"""Platform config service — DB-backed with a warm sync cache.

Dimensions drive every render and every request. ``get_format_info`` and
``validate_platforms`` are synchronous, so this service keeps a small TTL
cache refreshed from the ``platforms`` table: at lifespan, on every API
write, and once per ``generate_task`` (workers never run the FastAPI
lifespan). Before the first refresh the seed YAML is the fallback, so unit
tests and pre-boot reads still resolve dimensions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.config import get_settings

log = logging.getLogger(__name__)

_CACHE_TTL = 5.0
_platform_cache: list[dict] | None = None
_platform_cache_ts = 0.0

_VALID_FAMILIES = {"square", "portrait", "story", "landscape"}


@dataclass
class PlatformInfo:
    id: str
    name: str
    width: int
    height: int
    family: str
    is_active: bool = True


def platform_to_dict(row) -> dict:
    from app.core.time import iso_utc

    return {
        "id": row.id,
        "name": row.name,
        "width": row.width,
        "height": row.height,
        "family": row.family,
        "is_active": bool(row.is_active),
        "sort_order": row.sort_order,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
    }


def _yaml_seed() -> list[dict]:
    """Seed-platform fallback (pre-boot / unit tests, before DB is loaded).

    Family mirrors the DB seed: design-instruction ``format_families`` first,
    aspect heuristic otherwise.
    """
    from pathlib import Path

    from app.services.design_instruction import load_design_instruction
    from app.services.tokens import load_platforms

    settings = get_settings()
    dims = load_platforms(settings.platforms_path)
    di = load_design_instruction(Path(settings.design_system_dir) / "design-instruction.yaml")
    families = di.get("format_families", {}) if isinstance(di, dict) else {}
    out = []
    for i, (pid, (w, h)) in enumerate(sorted(dims.items())):
        fam = families.get(pid)
        if fam not in ("square", "portrait", "story", "landscape"):
            fam = "square" if h <= w else "portrait"
        out.append(
            {
                "id": pid,
                "name": pid.replace("-", " ").title(),
                "width": w,
                "height": h,
                "family": fam,
                "is_active": True,
                "sort_order": i,
            }
        )
    return out


async def refresh_platforms(pool=None) -> None:
    """Reload the platform cache from the DB (lifespan, writes, workers)."""
    global _platform_cache, _platform_cache_ts
    try:
        from app.db.repositories.platforms import PlatformRepository
        from app.db.session import get_shared_session_factory

        pool = pool or (await get_shared_session_factory())
        async with pool() as session:
            rows = await PlatformRepository(session).list(include_inactive=True)
        _platform_cache = [platform_to_dict(r) for r in rows]
        _platform_cache_ts = time.monotonic()
    except Exception as e:  # noqa: BLE001
        log.warning("[platforms] refresh failed: %s", e)


def _platforms() -> list[dict]:
    global _platform_cache, _platform_cache_ts
    now = time.monotonic()
    if _platform_cache is not None:
        if now - _platform_cache_ts < _CACHE_TTL:
            return _platform_cache
        return _platform_cache  # stale is fine; async refresh happens on writes
    return _yaml_seed()


def list_platforms(include_inactive: bool = False) -> list[dict]:
    rows = _platforms()
    if include_inactive:
        return rows
    return [r for r in rows if r.get("is_active", True)]


def get_platform(platform_id: str) -> dict | None:
    for r in _platforms():
        if r["id"] == platform_id:
            return r
    return None


def get_platform_dims(platform_id: str) -> tuple[int, int] | None:
    row = get_platform(platform_id)
    if row is None:
        return None
    return int(row["width"]), int(row["height"])


def family_of(platform_id: str) -> str:
    row = get_platform(platform_id)
    if row and row.get("family") in _VALID_FAMILIES:
        return row["family"]
    # Carousel slide ids (instagram-carousel-N / instagram-carousel-portrait-N)
    # resolve to their base platform's family.
    import re as _re

    m = _re.match(r"^(.+)-(\d+)$", platform_id)
    base = m.group(1) if m else platform_id
    row = get_platform(base)
    if row and row.get("family") in _VALID_FAMILIES:
        return row["family"]
    dims = get_platform_dims(base)
    if dims:
        w, h = dims
        return "square" if h <= w else "portrait"
    return "square"
