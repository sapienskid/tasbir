"""Cross-post novelty ledger (Redis, best-effort).

The composer itself is pure: it only avoids what the caller tells it to avoid.
This module supplies the "what did this design system just publish" list, so
consecutive posts do not repeat the same subject/relation/field combination.

Failure is always silent — an unavailable Redis must never block a post.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_TTL_SECONDS = 60 * 60 * 24 * 30
_LIMIT = 24


def _key(design_system_id: str) -> str:
    return f"tasbir:art:recent:{design_system_id or 'default'}"


async def recent_fingerprints(design_system_id: str, limit: int = _LIMIT) -> list[str]:
    """The most recent composition fingerprints for a design system, newest first."""
    try:
        from redis.asyncio import from_url

        from app.config import get_settings

        client = from_url(get_settings().redis_url, decode_responses=True)
        try:
            values = await client.lrange(_key(design_system_id), 0, max(limit - 1, 0))
        finally:
            await client.aclose()
        return [str(v) for v in values]
    except Exception as e:  # noqa: BLE001
        log.debug("[art] recent fingerprints unavailable: %s", e)
        return []


async def remember_fingerprints(design_system_id: str, fingerprints: list[str]) -> None:
    """Record compositions just published by a design system."""
    values = [fp for fp in fingerprints if fp]
    if not values:
        return
    try:
        from redis.asyncio import from_url

        from app.config import get_settings

        client = from_url(get_settings().redis_url, decode_responses=True)
        try:
            key = _key(design_system_id)
            await client.lpush(key, *values)
            await client.ltrim(key, 0, _LIMIT - 1)
            await client.expire(key, _TTL_SECONDS)
        finally:
            await client.aclose()
    except Exception as e:  # noqa: BLE001
        log.debug("[art] could not record fingerprints: %s", e)


__all__ = ["recent_fingerprints", "remember_fingerprints"]
