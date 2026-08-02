"""Runtime settings (tuning knobs) — DB-backed (seed-once), Studio-owned.

Replaces hardcoded pipeline constants: verifier retries, copywriter
concurrency, vision min-interval, chat HTML cap, template anti-repeat.
Env variables still own infra/secrets; these own behavioral tuning.
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

_SETTINGS_TTL = 5.0
_cache: dict[str, Any] | None = None
_cache_ts = 0.0

# key → {"value": default, "description": human hint}
DEFAULT_APP_SETTINGS: dict[str, dict] = {
    "verifier.max_retries": {
        "value": 2,
        "description": "Max verifier retry loops per format before failing",
    },
    "copywriter.concurrency": {
        "value": 2,
        "description": "Max concurrent copywriter LLM calls (Gemini free tier)",
    },
    "vision.min_interval_seconds": {
        "value": 5.0,
        "description": "Min seconds between vision LLM calls (rate limit)",
    },
    "chat.html_cap_chars": {
        "value": 80000,
        "description": "Max current-HTML chars shown to the editor chat agent",
    },
    "templates.recent_limit": {
        "value": 8,
        "description": "Anti-repeat: how many recently-used template ids to exclude",
    },
}


def invalidate_runtime_settings() -> None:
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


def _defaults() -> dict[str, Any]:
    return {k: v["value"] for k, v in DEFAULT_APP_SETTINGS.items()}


async def refresh_runtime_settings(pool=None) -> None:
    global _cache, _cache_ts
    try:
        from app.db.repositories.app_settings import AppSettingRepository
        from app.db.session import get_shared_session_factory

        pool = pool or (await get_shared_session_factory())
        merged = _defaults()
        async with pool() as session:
            rows = await AppSettingRepository(session).list()
        for r in rows:
            merged[r.key] = r.value
        _cache = merged
        _cache_ts = time.monotonic()
    except Exception as e:  # noqa: BLE001
        log.warning("[settings] refresh failed: %s", e)


def _resolved() -> dict[str, Any]:
    global _cache, _cache_ts
    now = time.monotonic()
    if _cache is not None:
        if now - _cache_ts < _SETTINGS_TTL:
            return _cache
        return _cache  # stale ok; async refresh happens on writes
    return _defaults()


async def get_runtime_setting(name: str, default: Any = None) -> Any:
    return _resolved().get(name, default)


async def get_runtime_settings() -> dict[str, Any]:
    return dict(_resolved())


async def update_runtime_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Upsert the given keys; returns the full resolved settings."""
    from app.db.repositories.app_settings import AppSettingRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        repo = AppSettingRepository(session)
        for key, value in values.items():
            if key not in DEFAULT_APP_SETTINGS:
                continue
            existing = await repo.get(key)
            if existing is None:
                await repo.create(key, value, DEFAULT_APP_SETTINGS[key]["description"])
            else:
                await repo.update(key, value)
    invalidate_runtime_settings()
    await refresh_runtime_settings(pool)
    return await get_runtime_settings()


async def reset_runtime_settings() -> dict[str, Any]:
    """Restore every knob to its default value."""
    from app.db.repositories.app_settings import AppSettingRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        repo = AppSettingRepository(session)
        for key, meta in DEFAULT_APP_SETTINGS.items():
            await repo.update(key, meta["value"], meta["description"])
    invalidate_runtime_settings()
    await refresh_runtime_settings(pool)
    return await get_runtime_settings()


async def seed_app_settings(pool) -> int:
    """Create missing setting rows from defaults (idempotent, seed-once)."""
    from app.db.repositories.app_settings import AppSettingRepository

    created = 0
    async with pool() as session:
        repo = AppSettingRepository(session)
        for key, meta in DEFAULT_APP_SETTINGS.items():
            if await repo.get(key) is None:
                await repo.create(key, meta["value"], meta["description"])
                created += 1
    if created:
        log.info("[settings] Seeded %d runtime setting(s)", created)
    invalidate_runtime_settings()
    await refresh_runtime_settings(pool)
    return created
