"""Image loader — downloads images and prepares them for embedding.

Validates each URL against the SSRF policy before fetching, enforces a
size cap, limits redirects, and checks the content type is an image.
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.config import get_settings
from app.services.ssrf import check_image_url

log = logging.getLogger(__name__)


async def prepare_images(images: list[dict] | None) -> list[dict]:
    """Download images from URLs and encode as base64 data URIs.

    Input: [{url, alt, description, placement}]
    Output: [{data (base64), alt, description, placement, mime}]
    """
    if not images:
        return []

    settings = get_settings()
    result = []
    max_bytes = settings.image_max_bytes
    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        max_redirects=settings.image_max_redirects,
    ) as client:
        for img in images:
            url = img.get("url", "")
            if not url:
                continue
            try:
                check_image_url(url)
                resp = await client.get(url)
                resp.raise_for_status()

                content_type = (
                    (resp.headers.get("content-type", "") or "").split(";")[0].strip().lower()
                )
                if content_type and not content_type.startswith("image/"):
                    log.warning("[image_loader] Skipped %s — content-type %s", url, content_type)
                    continue

                raw = resp.content
                if len(raw) > max_bytes:
                    log.warning("[image_loader] Skipped %s — %d bytes exceeds cap", url, len(raw))
                    continue

                mime = content_type or "image/png"
                b64 = base64.b64encode(raw).decode("ascii")
                result.append({
                    "data": b64,
                    "mime": mime,
                    "alt": img.get("alt", ""),
                    "description": img.get("description", ""),
                    "placement": img.get("placement", "auto"),
                })
                log.info("[image_loader] Loaded %s (%d bytes, %s)", url, len(raw), mime)
            except Exception as e:
                log.warning("[image_loader] Failed to load %s: %s", url, e)

    return result
