"""Penpot I/O service — read and write .penpot files (ZIP + JSON).

.penpot files are ZIP archives with:
  manifest.json         — file index
  files/{file-id}.json  — file metadata (name, pages list)
  files/{file-id}/data  — page data with shapes (TRANSIT+JSON encoded)
  objects/              — embedded binary assets (images, SVGs)

This service provides:
  - PenpotReader: read tokens + template boards from the Design System file
  - PenpotWriter: build a new .penpot file from scratch with boards + shapes
"""

from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design token CSS variable → value map (from AGENTS.md)
# These are the DEFAULT token values when no Design System file is present.
# ---------------------------------------------------------------------------
DEFAULT_TOKEN_VALUES: dict[str, str] = {
    "--color-bg": "#0f172a",
    "--color-bg-secondary": "#1e293b",
    "--color-text": "#ffffff",
    "--color-text-secondary": "#94a3b8",
    "--color-primary": "#667eea",
    "--color-secondary": "#764ba2",
    "--color-accent": "#6366f1",
    "--color-border": "#334155",
    "--font-sans": "Inter, sans-serif",
    "--font-serif": "Instrument Serif, serif",
    "--font-mono": "JetBrains Mono, monospace",
    "--radius-sm": "4px",
    "--radius-md": "8px",
    "--shadow-md": "0 4px 6px rgba(0,0,0,0.3)",
}

# ---------------------------------------------------------------------------
# Shape dataclasses (mirrors the .penpot JSON shape schema)
# ---------------------------------------------------------------------------


@dataclass
class Fill:
    color: str = "#000000"
    opacity: float = 1.0
    fill_type: str = "color"  # color | gradient | image

    def to_dict(self) -> dict:
        return {
            "fill-color": self.color,
            "fill-opacity": self.opacity,
            "fill-type": self.fill_type,
        }


@dataclass
class TextContent:
    text: str
    font_family: str = "Inter"
    font_size: float = 16.0
    font_weight: int = 400
    color: str = "#ffffff"
    line_height: float = 1.4
    letter_spacing: float = 0.0
    text_align: str = "left"  # left | center | right | justify

    def to_dict(self) -> dict:
        return {
            "type": "root",
            "children": [
                {
                    "type": "paragraph-set",
                    "children": [
                        {
                            "type": "paragraph",
                            "children": [
                                {
                                    "text": self.text,
                                    "font-family": self.font_family,
                                    "font-size": str(self.font_size),
                                    "font-weight": str(self.font_weight),
                                    "fill-color": self.color,
                                    "fill-opacity": 1,
                                    "line-height": str(self.line_height),
                                    "letter-spacing": str(self.letter_spacing),
                                    "text-align": self.text_align,
                                }
                            ],
                        }
                    ],
                }
            ],
        }


@dataclass
class PenpotShape:
    """Represents a shape in a Penpot page."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Shape"
    shape_type: str = "rect"  # frame | text | rect | svg-raw | image | group
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 100.0
    fills: list[Fill] = field(default_factory=list)
    children: list["PenpotShape"] = field(default_factory=list)
    rotation: float = 0.0
    opacity: float = 1.0
    blend_mode: str = "normal"
    # Text-specific
    text_content: TextContent | None = None
    # SVG-specific
    svg_content: str | None = None
    # Image-specific
    image_object_id: str | None = None
    # Frame-specific
    clip_content: bool = True
    frame_type: str = "none"  # none | grid | flex

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "type": self.shape_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "blend-mode": self.blend_mode,
            "fills": [f.to_dict() for f in self.fills],
            "strokes": [],
            "shadow": [],
        }

        if self.shape_type == "frame":
            d["clip-content"] = self.clip_content
            d["shapes"] = [c.id for c in self.children]
            d["frame-id"] = d["id"]

        elif self.shape_type == "text" and self.text_content:
            d["content"] = self.text_content.to_dict()

        elif self.shape_type == "svg-raw" and self.svg_content:
            d["content"] = self.svg_content

        elif self.shape_type == "image" and self.image_object_id:
            d["metadata"] = {"id": self.image_object_id}

        return d

    def flatten(self) -> list["PenpotShape"]:
        """Return self + all descendants in a flat list."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result


# ---------------------------------------------------------------------------
# PenpotWriter — builds a complete .penpot ZIP from scratch
# ---------------------------------------------------------------------------


class PenpotWriter:
    """Build a .penpot ZIP file containing one or more boards.

    Usage:
        writer = PenpotWriter(file_name="Generated Design")
        writer.add_board("instagram-square", 1080, 1080, board_shape)
        data = writer.build()
        Path("output.penpot").write_bytes(data)
    """

    def __init__(self, file_name: str = "Tasbir Generated"):
        self.file_name = file_name
        self.file_id = str(uuid.uuid4())
        self.pages: list[dict] = []  # [{id, name, shapes: [PenpotShape]}]
        self._objects: dict[str, bytes] = {}  # object_id → bytes

    def add_board(
        self,
        page_name: str,
        width: int,
        height: int,
        root_shape: PenpotShape,
    ) -> str:
        """Add a board (page) to the file. Returns the page ID."""
        page_id = str(uuid.uuid4())
        # Ensure root is a frame spanning full canvas
        root_shape.shape_type = "frame"
        root_shape.x = 0.0
        root_shape.y = 0.0
        root_shape.width = float(width)
        root_shape.height = float(height)
        self.pages.append({
            "id": page_id,
            "name": page_name,
            "width": width,
            "height": height,
            "root": root_shape,
        })
        return page_id

    def add_object(self, data: bytes, media_type: str = "image/png") -> str:
        """Embed a binary object (image/SVG). Returns the object ID."""
        obj_id = str(uuid.uuid4())
        self._objects[obj_id] = data
        return obj_id

    def build(self) -> bytes:
        """Build and return the .penpot ZIP bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. manifest.json
            manifest = self._build_manifest()
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # 2. File metadata
            file_meta = self._build_file_meta()
            zf.writestr(f"files/{self.file_id}.json", json.dumps(file_meta, indent=2))

            # 3. Pages (data)
            pages_data = self._build_pages_data()
            for page_id, page_data in pages_data.items():
                zf.writestr(
                    f"files/{self.file_id}/pages/{page_id}",
                    json.dumps(page_data, indent=2),
                )

            # 4. Embedded objects
            for obj_id, obj_bytes in self._objects.items():
                zf.writestr(f"objects/{obj_id}", obj_bytes)

        buf.seek(0)
        return buf.read()

    def _build_manifest(self) -> dict:
        return {
            "format": 2,
            "files": {
                self.file_id: {
                    "name": self.file_name,
                    "features": [],
                }
            },
        }

    def _build_file_meta(self) -> dict:
        return {
            "id": self.file_id,
            "name": self.file_name,
            "pages": [p["id"] for p in self.pages],
            "pages-index": {
                p["id"]: {"name": p["name"], "id": p["id"]}
                for p in self.pages
            },
            "colors": {},
            "typographies": {},
            "components": {},
            "data": {
                "id": self.file_id,
                "name": self.file_name,
            },
        }

    def _build_pages_data(self) -> dict[str, dict]:
        result = {}
        for page in self.pages:
            page_id = page["id"]
            root: PenpotShape = page["root"]

            # Flatten all shapes
            all_shapes = root.flatten()
            objects_dict: dict[str, Any] = {}

            # Root frame ID is the page's frame
            page_frame_id = root.id

            for shape in all_shapes:
                shape_dict = shape.to_dict()
                # Set frame-id for all shapes (points to root frame)
                if shape.id != page_frame_id:
                    shape_dict["frame-id"] = page_frame_id
                    shape_dict["parent-id"] = self._find_parent_id(root, shape.id)
                else:
                    shape_dict["frame-id"] = page_frame_id
                    shape_dict["parent-id"] = "00000000-0000-0000-0000-000000000000"
                objects_dict[shape.id] = shape_dict

            # Add the special root "frame" that Penpot expects
            # (a transparent container for the whole page)
            root_frame_id = "00000000-0000-0000-0000-000000000000"
            objects_dict[root_frame_id] = {
                "id": root_frame_id,
                "name": "Root Frame",
                "type": "frame",
                "x": 0,
                "y": 0,
                "width": page["width"],
                "height": page["height"],
                "shapes": [root.id],
                "fills": [],
                "strokes": [],
                "shadow": [],
                "rotation": 0,
                "opacity": 1,
                "blend-mode": "normal",
                "clip-content": False,
                "frame-id": root_frame_id,
                "parent-id": None,
            }

            result[page_id] = {
                "id": page_id,
                "name": page["name"],
                "objects": objects_dict,
                "options": {
                    "background": "#e8e9ea",
                    "saved-grids": {},
                },
            }

        return result

    def _find_parent_id(self, root: PenpotShape, target_id: str) -> str:
        """Find the parent ID of a shape in the tree."""
        def _search(shape: PenpotShape) -> str | None:
            for child in shape.children:
                if child.id == target_id:
                    return shape.id
                found = _search(child)
                if found:
                    return found
            return None

        found = _search(root)
        return found or root.id


# ---------------------------------------------------------------------------
# PenpotReader — extract tokens from an existing .penpot file
# ---------------------------------------------------------------------------


class PenpotReader:
    """Read design tokens and template info from a .penpot file.

    Usage:
        reader = PenpotReader(path)
        tokens = reader.get_tokens()  # dict: css_var → value
        pages = reader.list_pages()
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._zip: zipfile.ZipFile | None = None
        self._manifest: dict | None = None
        self._file_id: str | None = None
        self._file_meta: dict | None = None
        self._tokens: dict[str, str] | None = None

    def _open(self) -> None:
        if not self.path.exists():
            log.warning("[PenpotReader] Design system file not found: %s — using defaults", self.path)
            return
        if self._zip is None:
            self._zip = zipfile.ZipFile(self.path, "r")

    def _load_manifest(self) -> dict:
        if self._manifest:
            return self._manifest
        self._open()
        if not self._zip:
            return {}
        try:
            with self._zip.open("manifest.json") as f:
                self._manifest = json.load(f)
                files = self._manifest.get("files", {})
                if files:
                    self._file_id = next(iter(files))
        except Exception as e:
            log.warning("[PenpotReader] Could not read manifest: %s", e)
            self._manifest = {}
        return self._manifest or {}

    def _load_file_meta(self) -> dict:
        if self._file_meta:
            return self._file_meta
        manifest = self._load_manifest()
        if not self._zip or not self._file_id:
            return {}
        try:
            meta_path = f"files/{self._file_id}.json"
            with self._zip.open(meta_path) as f:
                self._file_meta = json.load(f)
        except Exception as e:
            log.warning("[PenpotReader] Could not read file meta: %s", e)
            self._file_meta = {}
        return self._file_meta or {}

    def get_tokens(self) -> dict[str, str]:
        """Return CSS variable → value mapping from design tokens.

        Falls back to DEFAULT_TOKEN_VALUES if the file doesn't exist
        or doesn't contain a tokens.json.
        """
        if self._tokens is not None:
            return self._tokens

        self._open()
        if not self._zip:
            self._tokens = dict(DEFAULT_TOKEN_VALUES)
            return self._tokens

        # Try reading tokens.json from inside the .penpot
        token_paths = [
            "tokens.json",
            f"files/{self._file_id}/tokens.json" if self._file_id else None,
        ]
        for tp in token_paths:
            if not tp:
                continue
            try:
                with self._zip.open(tp) as f:
                    raw = json.load(f)
                self._tokens = self._parse_tokens(raw)
                return self._tokens
            except KeyError:
                continue
            except Exception as e:
                log.warning("[PenpotReader] Token parse error: %s", e)

        log.info("[PenpotReader] No tokens.json found, using defaults")
        self._tokens = dict(DEFAULT_TOKEN_VALUES)
        return self._tokens

    def _parse_tokens(self, raw: dict) -> dict[str, str]:
        """Parse DTCG token format into CSS variable map."""
        result = dict(DEFAULT_TOKEN_VALUES)

        # Handle flat format: {"--color-bg": "#0f172a", ...}
        if all(k.startswith("--") for k in raw.keys()):
            result.update(raw)
            return result

        # Handle DTCG nested format: {"color": {"semantic": {"bg": {"$value": "#0f172a"}}}}
        css_map = {
            "color.semantic.bg.default": "--color-bg",
            "color.semantic.bg.secondary": "--color-bg-secondary",
            "color.semantic.text.primary": "--color-text",
            "color.semantic.text.secondary": "--color-text-secondary",
            "color.brand.primary.main": "--color-primary",
            "color.brand.secondary.main": "--color-secondary",
            "color.brand.accent": "--color-accent",
            "color.semantic.border": "--color-border",
        }

        def _extract(obj: dict, prefix: str = "") -> None:
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    if "$value" in v:
                        css_var = css_map.get(path)
                        if css_var:
                            result[css_var] = str(v["$value"])
                    else:
                        _extract(v, path)

        _extract(raw)
        return result

    def list_pages(self) -> list[str]:
        """Return list of page names in the design system file."""
        meta = self._load_file_meta()
        pages_index = meta.get("pages-index", {})
        return [p.get("name", "") for p in pages_index.values()]

    def close(self) -> None:
        if self._zip:
            self._zip.close()
            self._zip = None

    def __enter__(self) -> "PenpotReader":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# CSS injection helper (used by html_to_penpot to resolve CSS vars)
# ---------------------------------------------------------------------------


def build_css_variable_block(tokens: dict[str, str]) -> str:
    """Build a CSS :root block with all token values for injection into HTML."""
    lines = [":root {"]
    for var, value in tokens.items():
        lines.append(f"  {var}: {value};")
    lines.append("}")
    return "\n".join(lines)


def inject_tokens_into_html(html: str, tokens: dict[str, str]) -> str:
    """Inject CSS variable definitions into an HTML document's <head>.

    This ensures the browser resolves all var(--color-*) correctly when
    Playwright renders the page.
    """
    css_block = build_css_variable_block(tokens)
    style_tag = f"<style>\n{css_block}\n</style>"

    # Insert after <head> or before </head> or before <body>
    if "<head>" in html:
        return html.replace("<head>", f"<head>\n{style_tag}", 1)
    if "</head>" in html:
        return html.replace("</head>", f"{style_tag}\n</head>", 1)
    if "<body" in html:
        idx = html.index("<body")
        return html[:idx] + style_tag + "\n" + html[idx:]

    return style_tag + "\n" + html
