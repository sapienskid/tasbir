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

import datetime
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
# Shape dataclasses (mirrors the .penpot v3 JSON shape schema — camelCase)
# ---------------------------------------------------------------------------

# All migrations a new Penpot 2.16 file has applied (from a real export)
_PENPOT_MIGRATIONS = [
    "legacy-2", "legacy-3", "legacy-5", "legacy-6", "legacy-7", "legacy-8",
    "legacy-9", "legacy-10", "legacy-11", "legacy-12", "legacy-13", "legacy-14",
    "legacy-16", "legacy-17", "legacy-18", "legacy-19", "legacy-25", "legacy-26",
    "legacy-27", "legacy-28", "legacy-29", "legacy-31", "legacy-32", "legacy-33",
    "legacy-34", "legacy-36", "legacy-37", "legacy-38", "legacy-39", "legacy-40",
    "legacy-41", "legacy-42", "legacy-43", "legacy-44", "legacy-45", "legacy-46",
    "legacy-47", "legacy-48", "legacy-49", "legacy-50", "legacy-51", "legacy-52",
    "legacy-53", "legacy-54", "legacy-55", "legacy-56", "legacy-57", "legacy-59",
    "legacy-62", "legacy-65", "legacy-66", "legacy-67",
    "0001-remove-tokens-from-groups", "0002-normalize-bool-content-v2",
    "0002-clean-shape-interactions", "0003-fix-root-shape",
    "0003-convert-path-content-v2", "0005-deprecate-image-type",
    "0006-fix-old-texts-fills", "0008-fix-library-colors-v4",
    "0009-clean-library-colors", "0009-add-partial-text-touched-flags",
    "0010-fix-swap-slots-pointing-non-existent-shapes",
    "0011-fix-invalid-text-touched-flags", "0012-fix-position-data",
    "0013-fix-component-path", "0013-clear-invalid-strokes-and-fills",
    "0014-fix-tokens-lib-duplicate-ids", "0014-clear-components-nil-objects",
    "0015-fix-text-attrs-blank-strings", "0015-clean-shadow-color",
    "0016-copy-fills-from-position-data-to-text-node", "0017-fix-layout-flex-dir",
    "0018-remove-unneeded-objects-from-components", "0019-fix-missing-swap-slots",
    "0020-sync-component-id-with-near-main", "0021-fix-shape-svg-attrs",
    "0022-normalize-component-root-and-resync",
]

_PENPOT_FEATURES = [
    "fdata/path-data", "design-tokens/v1", "variants/v1",
    "layout/grid", "components/v2", "fdata/shape-data-type",
]


@dataclass
class Fill:
    color: str = "#000000"
    opacity: float = 1.0
    fill_color_gradient: dict | None = None  # Penpot schema:gradient format
    # NOTE: do NOT include fill-type — Penpot's FillAttrs schema rejects it as an extra key

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "fill-color": self.color,
            "fill-opacity": self.opacity,
        }
        if self.fill_color_gradient:
            d["fill-color-gradient"] = dict(self.fill_color_gradient)
        return d


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
                                    "fontFamily": self.font_family,
                                    "fontSize": str(self.font_size),
                                    "fontWeight": str(self.font_weight),
                                    "fillColor": self.color,
                                    "fillOpacity": 1,
                                    "lineHeight": str(self.line_height),
                                    "letterSpacing": str(self.letter_spacing),
                                    "textAlign": self.text_align,
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

    # Border radius (per-corner, 0 = no rounding)
    r1: float = 0.0
    r2: float = 0.0
    r3: float = 0.0
    r4: float = 0.0

    # Strokes (borders) — list of dicts matching Penpot schema:stroke
    strokes: list[dict] = field(default_factory=list)

    # Shadow effects — list of dicts matching Penpot schema:shadow
    shadow: list[dict] = field(default_factory=list)

    # Layer blur — dict matching Penpot schema:blur, or None
    blur: dict | None = None

    # Text-specific
    text_content: TextContent | None = None
    # SVG-specific
    svg_content: str | None = None
    # Image-specific
    image_object_id: str | None = None
    image_width: int = 0
    image_height: int = 0
    image_mtype: str = "image/png"
    # Frame-specific
    clip_content: bool = True
    frame_type: str = "none"  # none | grid | flex

    def to_dict(self) -> dict:
        w = max(self.width, 1.0)
        h = max(self.height, 1.0)
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "type": self.shape_type,
            "x": self.x,
            "y": self.y,
            "width": w,
            "height": h,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "blendMode": self.blend_mode,
            "fills": [f.to_dict() for f in self.fills],
            "strokes": list(self.strokes),
            "shadow": list(self.shadow),
            "r1": self.r1,
            "r2": self.r2,
            "r3": self.r3,
            "r4": self.r4,
            "selrect": {
                "x": self.x, "y": self.y,
                "width": w, "height": h,
                "x1": self.x, "y1": self.y,
                "x2": self.x + w, "y2": self.y + h,
            },
            "points": [
                {"x": self.x, "y": self.y},
                {"x": self.x + w, "y": self.y},
                {"x": self.x + w, "y": self.y + h},
                {"x": self.x, "y": self.y + h},
            ],
            "transform": {"a": 1, "b": 0, "c": 0, "d": 1, "e": 0, "f": 0},
            "transformInverse": {"a": 1, "b": 0, "c": 0, "d": 1, "e": 0, "f": 0},
            "hideFillOnExport": False,
        }

        if self.blur:
            d["blur"] = dict(self.blur)

        if self.shape_type == "frame":
            d["clipContent"] = self.clip_content
            d["shapes"] = [c.id for c in self.children]

        elif self.shape_type == "text" and self.text_content:
            d["content"] = self.text_content.to_dict()
            d["shapes"] = []

        elif self.shape_type == "svg-raw" and self.svg_content:
            d["content"] = self.svg_content
            d["shapes"] = []

        elif self.shape_type == "image" and self.image_object_id:
            d["metadata"] = {
                "id": self.image_object_id,
                "width": self.image_width,
                "height": self.image_height,
                "mtype": self.image_mtype,
            }
            d["shapes"] = []

        return d

    def flatten(self) -> list["PenpotShape"]:
        """Return self + all descendants in a flat list."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result


# ---------------------------------------------------------------------------
# Helper factories for Penpot-compatible stroke, shadow, blur dicts
# These produce dicts matching the Penpot Clojure schemas exactly.
# ---------------------------------------------------------------------------


def make_stroke(
    color: str = "#000000",
    opacity: float = 1.0,
    width: float = 1.0,
    style: str = "solid",
    alignment: str = "inner",
) -> dict:
    """Build a stroke dict matching Penpot schema:stroke-attrs."""
    return {
        "stroke-color": color,
        "stroke-opacity": opacity,
        "stroke-width": width,
        "stroke-style": style,
        "stroke-alignment": alignment,
    }


def make_shadow(
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    blur: float = 4.0,
    spread: float = 0.0,
    color: str = "#000000",
    opacity: float = 0.3,
    style: str = "drop-shadow",
) -> dict:
    """Build a shadow dict matching Penpot schema:shadow."""
    return {
        "style": style,
        "offset-x": offset_x,
        "offset-y": offset_y,
        "blur": blur,
        "spread": spread,
        "hidden": False,
        "color": {"color": color, "opacity": opacity},
    }


def make_blur(value: float = 0.0) -> dict:
    """Build a blur dict matching Penpot schema:blur."""
    return {
        "type": "layer-blur",
        "value": value,
        "hidden": False,
    }


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
        self._object_metas: dict[str, dict] = {}  # object_id → storage metadata
        self._media_refs: dict[str, dict] = {}  # media_id → media reference

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

    def add_image(self, data: bytes, name: str = "image") -> str:
        """Embed a PNG image as a Penpot media object.

        Creates storage object + media reference.
        Returns the media ID to use in an image shape's metadata.
        """
        import hashlib

        obj_id = str(uuid.uuid4())
        media_id = str(uuid.uuid4())

        # Store binary
        self._objects[obj_id] = data

        # Store object metadata
        mtime = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        obj_meta = {
            "id": obj_id,
            "size": len(data),
            "contentType": "image/png",
            "bucket": "file-media-object",
            "hash": f"blake2b:{hashlib.blake2b(data).hexdigest()}",
            "createdAt": mtime,
        }
        self._object_metas[obj_id] = obj_meta

        # Store media reference
        try:
            from PIL import Image
            import io as _io
            img = Image.open(_io.BytesIO(data))
            width, height = img.size
        except Exception:
            width, height = 1080, 1080

        media_ref = {
            "id": media_id,
            "name": name,
            "width": width,
            "height": height,
            "mtype": "image/png",
            "mediaId": obj_id,
            "isLocal": True,
        }
        self._media_refs[media_id] = media_ref

        return media_id

    def build(self) -> bytes:
        """Build and return the .penpot ZIP bytes in Penpot v3 binfile format."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. manifest.json
            manifest = self._build_manifest()
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # 2. File metadata
            file_meta = self._build_file_meta()
            zf.writestr(f"files/{self.file_id}.json", json.dumps(file_meta, indent=2))

            # 3. Pages & shapes
            for idx, page in enumerate(self.pages):
                page_id = page["id"]
                page_meta = {"id": page_id, "name": page["name"], "index": idx}
                zf.writestr(
                    f"files/{self.file_id}/pages/{page_id}.json",
                    json.dumps(page_meta, indent=2),
                )

                shapes = self._build_page_shapes(page)
                for shape_id, shape_data in shapes.items():
                    zf.writestr(
                        f"files/{self.file_id}/pages/{page_id}/{shape_id}.json",
                        json.dumps(shape_data, indent=2),
                    )

            # 4. Media references
            for media_id, media_ref in self._media_refs.items():
                zf.writestr(
                    f"files/{self.file_id}/media/{media_id}.json",
                    json.dumps(media_ref, indent=2),
                )

            # 5. Storage objects (binary + metadata)
            for obj_id, obj_bytes in self._objects.items():
                mtype = self._object_metas.get(obj_id, {}).get("contentType", "image/png")
                ext = mtype.split("/")[-1] if "/" in mtype else "bin"
                zf.writestr(f"objects/{obj_id}.{ext}", obj_bytes)
                if obj_id in self._object_metas:
                    zf.writestr(
                        f"objects/{obj_id}.json",
                        json.dumps(self._object_metas[obj_id], indent=2),
                    )

        buf.seek(0)
        return buf.read()

    def _build_manifest(self) -> dict:
        return {
            "type": "penpot/export-files",
            "version": 1,
            "generatedBy": "tasbir/1.0",
            "refer": "penpot",
            "files": [
                {
                    "id": self.file_id,
                    "name": self.file_name,
                    "features": _PENPOT_FEATURES,
                }
            ],
            "relations": [],
        }

    def _build_file_meta(self) -> dict:
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return {
            "id": self.file_id,
            "name": self.file_name,
            "vern": 0,
            "revn": 1,
            "version": 67,
            "hasMediaTrimmed": False,
            "isShared": False,
            "createdAt": now_str,
            "modifiedAt": now_str,
            "features": _PENPOT_FEATURES,
            "migrations": _PENPOT_MIGRATIONS,
            "pages": [p["id"] for p in self.pages],
            "pages-index": {
                p["id"]: {"name": p["name"], "id": p["id"]}
                for p in self.pages
            },
            "options": {
                "componentsV2": True,
                "baseFontSize": "16px",
            },
        }

    def _build_page_shapes(self, page: dict) -> dict[str, dict]:
        page_id = page["id"]
        root: PenpotShape = page["root"]

        all_shapes = root.flatten()
        result: dict[str, Any] = {}

        page_frame_id = root.id

        for shape in all_shapes:
            shape_dict = shape.to_dict()
            shape_dict["pageId"] = page_id
            if shape.id != page_frame_id:
                shape_dict["frameId"] = page_frame_id
                shape_dict["parentId"] = self._find_parent_id(root, shape.id)
            else:
                shape_dict["frameId"] = page_frame_id
                shape_dict["parentId"] = "00000000-0000-0000-0000-000000000000"
            result[shape.id] = shape_dict

        # Special root frame required by Penpot
        root_frame_id = "00000000-0000-0000-0000-000000000000"
        result[root_frame_id] = {
            "id": root_frame_id,
            "name": "Root Frame",
            "type": "frame",
            "x": 0,
            "y": 0,
            "width": page["width"],
            "height": page["height"],
            "rotation": 0,
            "selrect": {
                "x": 0, "y": 0,
                "width": page["width"], "height": page["height"],
                "x1": 0, "y1": 0,
                "x2": page["width"], "y2": page["height"],
            },
            "points": [
                {"x": 0, "y": 0},
                {"x": page["width"], "y": 0},
                {"x": page["width"], "y": page["height"]},
                {"x": 0, "y": page["height"]},
            ],
            "transform": {"a": 1, "b": 0, "c": 0, "d": 1, "e": 0, "f": 0},
            "transformInverse": {"a": 1, "b": 0, "c": 0, "d": 1, "e": 0, "f": 0},
            "parentId": root_frame_id,
            "frameId": root_frame_id,
            "pageId": page_id,
            "shapes": [root.id],
            "fills": [],
            "strokes": [],
            "shadow": [],
            "opacity": 1,
            "blendMode": "normal",
            "clipContent": False,
            "hideFillOnExport": False,
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
                files = self._manifest.get("files", [])
                if isinstance(files, list) and files:
                    self._file_id = files[0].get("id")
                elif isinstance(files, dict):
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
