"""Curated Google Fonts pool — DB-backed (seed-once), Studio-owned.

The brand_tokens agent chooses display/serif/sans ONLY from this pool.
Runtime reads resolve from the ``fonts`` table; the seed YAML is the
pre-boot / unit-test fallback.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

_FONT_CACHE_TTL = 5.0
_font_cache: list[dict] | None = None
_font_cache_ts = 0.0


def font_to_dict(row) -> dict:
    from app.core.time import iso_utc

    return {
        "family": row.family,
        "role": row.role,
        "weights": row.weights or [],
        "style": row.style,
        "is_active": bool(row.is_active),
        "sort_order": row.sort_order,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
    }


def _yaml_seed() -> list[dict]:
    path = _fonts_path()
    if not path.exists():
        return []
    try:
        with open(path) as f:
            import yaml

            raw = yaml.safe_load(f)
        fonts = raw.get("fonts", []) if isinstance(raw, dict) else []
        return [
            {
                "family": f.get("family", ""),
                "role": f.get("role", "sans"),
                "weights": list(f.get("weights", []) or []),
                "style": f.get("style", ""),
                "is_active": True,
                "sort_order": i,
            }
            for i, f in enumerate(fonts)
            if isinstance(f, dict) and f.get("family")
        ]
    except Exception as e:  # noqa: BLE001
        log.warning("[fonts] YAML seed failed: %s", e)
        return []


def _fonts_path():
    from pathlib import Path

    from app.config import get_settings

    return Path(get_settings().design_system_dir) / "fonts.yaml"


async def refresh_font_pool(pool=None) -> None:
    global _font_cache, _font_cache_ts
    try:
        from app.db.repositories.fonts import FontRepository
        from app.db.session import get_shared_session_factory

        pool = pool or (await get_shared_session_factory())
        async with pool() as session:
            rows = await FontRepository(session).list(include_inactive=True)
        _font_cache = [font_to_dict(r) for r in rows]
        _font_cache_ts = time.monotonic()
    except Exception as e:  # noqa: BLE001
        log.warning("[fonts] refresh failed: %s", e)


def _fonts() -> list[dict]:
    global _font_cache, _font_cache_ts
    now = time.monotonic()
    if _font_cache is not None:
        if now - _font_cache_ts < _FONT_CACHE_TTL:
            return _font_cache
        return _font_cache
    return _yaml_seed()


async def load_font_pool() -> list[dict]:
    """Active curated font pool from the DB (YAML seed fallback)."""
    return [f for f in _fonts() if f.get("is_active", True)]


async def font_pool_for_prompt() -> str:
    """Format the pool for the brand_tokens agent (families + roles + weights)."""
    lines = []
    for f in await load_font_pool():
        fam = f.get("family", "")
        role = f.get("role", "sans")
        weights = ", ".join(str(w) for w in f.get("weights", [])) or "400"
        lines.append(f"  {fam} [{role}, weights {weights}]")
    return "\n".join(lines) or "  (none)"
