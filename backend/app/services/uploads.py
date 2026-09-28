"""Upload validation — magic-byte sniffing for raster images.

No Pillow dependency: we validate the first bytes of the file rather than
relying on the declared content type. Returns base64 data for embedding.
"""

from __future__ import annotations

import base64
import logging

from app.config import get_settings

log = logging.getLogger(__name__)

_MAGIC: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}
# WebP RIFF....WEBP (12-byte header).
_WEBP_MAGIC = b"WEBP"


def sniff_mime(raw: bytes) -> str | None:
    """Return the image mime type from magic bytes, or None if not an image."""
    for magic, mime in _MAGIC.items():
        if raw.startswith(magic):
            return mime
    if raw.startswith(b"RIFF") and len(raw) > 12 and raw[8:12] == _WEBP_MAGIC:
        return "image/webp"
    return None


def validate_upload(raw: bytes) -> tuple[str, str]:
    """Validate uploaded image bytes → (mime, base64). Raises ValueError."""
    settings = get_settings()
    if not raw:
        raise ValueError("Empty file")
    if len(raw) > settings.image_max_bytes:
        raise ValueError(
            f"Image too large (max {settings.image_max_bytes} bytes)"
        )
    mime = sniff_mime(raw)
    if mime is None:
        raise ValueError("Unsupported file type — use PNG, JPEG, WebP, or GIF")
    return mime, base64.b64encode(raw).decode("ascii")


def sniff_logo_mime(raw: bytes) -> str | None:
    """Image mime for logos — raster types plus SVG (safe in <img> context).

    The bundled seed accepts ``.svg`` logos; the Studio upload path should
    too. SVG never reaches vision/LLM inputs — it is only ever injected as an
    ``<img src="data:…">`` where scripts do not execute.
    """
    mime = sniff_mime(raw)
    if mime is not None:
        return mime
    head = raw.lstrip()[:1024]
    if head.startswith(b"<svg") or (
        head.startswith(b"<?xml") and b"<svg" in head
    ):
        return "image/svg+xml"
    return None


def validate_logo_upload(raw: bytes) -> tuple[str, str]:
    """Validate an uploaded logo (raster or SVG) → (mime, base64). Raises ValueError."""
    settings = get_settings()
    if not raw:
        raise ValueError("Empty file")
    if len(raw) > settings.image_max_bytes:
        raise ValueError(
            f"Image too large (max {settings.image_max_bytes} bytes)"
        )
    mime = sniff_logo_mime(raw)
    if mime is None:
        raise ValueError("Unsupported file type — use PNG, JPEG, WebP, GIF, or SVG")
    return mime, base64.b64encode(raw).decode("ascii")
