"""Image loader — downloads images and prepares them for embedding."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


async def prepare_images(images: list[dict] | None) -> list[dict]:
    """Download images from URLs and encode as base64 data URIs.

    Input: [{url, alt, description, placement}]
    Output: [{data (base64), alt, description, placement, mime}]
    """
    if not images:
        return []

    result = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for img in images:
            url = img.get("url", "")
            if not url:
                continue
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                raw = resp.content
                mime = resp.headers.get("content-type", "image/png")
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
