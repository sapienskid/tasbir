"""Penpot I/O service — read design tokens from .penpot files.

The .penpot reader extracts CSS variable → value mappings from the
Design System file for injection into generated HTML.

This service also provides:
  - DEFAULT_TOKEN_VALUES: fallback tokens when no Design System file exists
  - inject_tokens_into_html: resolves CSS variables in HTML before rendering
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design token CSS variable → value map (from AGENTS.md)
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
