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


class SettingError(ValueError):
    """One or more runtime-setting values failed validation.

    Raised before anything is written so a rejected PUT leaves the DB untouched.
    """

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


# key → {
#   "value":       default,
#   "type":        "int" | "float" | "bool",
#   "min"/"max":   inclusive bounds (numeric only),
#   "step":        UI step hint (numeric only),
#   "description": human hint,
# }
# The type contract is the single source of truth for BOTH server-side
# validation and the Studio's control rendering, so the UI needs no hardcoded
# per-key knowledge.
DEFAULT_APP_SETTINGS: dict[str, dict] = {
    "verifier.max_retries": {
        "value": 3,
        "type": "int",
        "min": 0,
        "max": 10,
        "step": 1,
        "description": "Max verifier retry loops per format before failing",
    },
    "copywriter.concurrency": {
        "value": 2,
        "type": "int",
        "min": 1,
        "max": 16,
        "step": 1,
        "description": "Max concurrent copywriter LLM calls (parallel, like the original design)",
    },
    "copywriter.qa_max_rounds": {
        "value": 1,
        "type": "int",
        "min": 0,
        "max": 5,
        "step": 1,
        "description": "Decision-driven copy QA rewrite rounds (0 disables the copy loop)",
    },
    "vision.min_interval_seconds": {
        "value": 5.0,
        "type": "float",
        "min": 0.0,
        "max": 300.0,
        "step": 0.5,
        "description": "Min seconds between vision LLM calls (vision-only pacing)",
    },
    "chat.html_cap_chars": {
        "value": 80000,
        "type": "int",
        "min": 1000,
        "max": 2_000_000,
        "step": 1000,
        "description": "Max current-HTML chars shown to the editor chat agent",
    },
    "templates.recent_limit": {
        "value": 8,
        "type": "int",
        "min": 0,
        "max": 100,
        "step": 1,
        "description": "Anti-repeat: how many recently-used template ids to exclude",
    },
    "verifier.clef_first": {
        "value": True,
        "type": "bool",
        "description": "Clef vision first; skip the Gemini audit on a clean pass",
    },
    "claims.hold_on_mismatch": {
        "value": True,
        "type": "bool",
        "description": "Hold publish when copy contains figures missing from the source",
    },
    "publish.enabled": {
        "value": True,
        "type": "bool",
        "description": "Record a per-format publish/hold gate in the task result",
    },
}


def invalidate_runtime_settings() -> None:
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


def _defaults() -> dict[str, Any]:
    return {k: v["value"] for k, v in DEFAULT_APP_SETTINGS.items()}


def _describe(key: str) -> str:
    spec = DEFAULT_APP_SETTINGS[key]
    if spec["type"] == "bool":
        return f"{key!r} must be true or false"
    return (
        f"{key!r} must be a number of type {spec['type']} "
        f"in [{spec.get('min')}, {spec.get('max')}]"
    )


def _coerce(key: str, raw: Any) -> Any:
    """Validate/convert one raw value against its knob's type contract.

    Raises ``SettingError`` describing the single offending key. Booleans are
    strict (``bool`` only, so the old ``Number()`` coercion bug — where a bool
    round-tripped through a number input became ``1``/``0`` — cannot recur).
    """
    spec = DEFAULT_APP_SETTINGS[key]
    kind = spec["type"]

    if kind == "bool":
        if not isinstance(raw, bool):
            raise SettingError([_describe(key)])
        return raw

    # bool is a subclass of int in Python: reject it explicitly for numeric knobs.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise SettingError([_describe(key)])

    lo, hi = spec.get("min"), spec.get("max")
    if lo is not None and raw < lo:
        raise SettingError([f"{key!r} must be >= {lo} (got {raw})"])
    if hi is not None and raw > hi:
        raise SettingError([f"{key!r} must be <= {hi} (got {raw})"])

    if kind == "int":
        if isinstance(raw, float) and not raw.is_integer():
            raise SettingError([f"{key!r} must be a whole number (got {raw})"])
        return int(raw)
    return float(raw)


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
            # Only known knobs: internal rows (e.g. the bundled-seed marker)
            # must not surface in the Studio's settings.
            if r.key not in merged:
                continue
            # Self-heal: a value written before the type contract existed (or
            # hand-edited in the DB) falls back to its default instead of
            # reaching a consumer that would crash on it.
            try:
                merged[r.key] = _coerce(r.key, r.value)
            except SettingError:
                log.warning(
                    "[settings] stored value for %r is invalid, using default %r",
                    r.key,
                    merged[r.key],
                )
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
    """Upsert the given keys; returns the full resolved settings.

    Unknown keys are ignored (forward compatibility: a newer Studio talking to
    an older API). Known keys are validated as a batch — if any value is bad,
    nothing is written and ``SettingError`` is raised.
    """
    from app.db.repositories.app_settings import AppSettingRepository
    from app.db.session import get_shared_session_factory

    # Validate the whole batch up front so a rejection is atomic.
    coerced: dict[str, Any] = {}
    problems: list[str] = []
    for key, raw in values.items():
        if key not in DEFAULT_APP_SETTINGS:
            continue
        try:
            coerced[key] = _coerce(key, raw)
        except SettingError as e:
            problems.extend(e.problems)
    if problems:
        raise SettingError(problems)

    pool = await get_shared_session_factory()
    async with pool() as session:
        repo = AppSettingRepository(session)
        for key, value in coerced.items():
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
            # update() is a no-op on a missing row, so create it instead of
            # silently resetting nothing.
            if await repo.get(key) is None:
                await repo.create(key, meta["value"], meta["description"])
            else:
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
