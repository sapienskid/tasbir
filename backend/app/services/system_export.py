"""System export/import — portable config backup for Tasbir.

Exports the DB-backed *configuration* tables (design systems, templates,
platforms, fonts, agents, runtime settings) as a single JSON document. Runtime
data (generation tasks, audit logs, chat threads, agent jobs) is deliberately
excluded — it is ephemeral, per-machine state.

Import uses upsert/merge semantics: rows are inserted or overwritten by primary
key, and rows already present but missing from the payload are left untouched.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.db.repositories.agents import AgentRepository
from app.db.repositories.app_settings import AppSettingRepository
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.fonts import FontRepository
from app.db.repositories.platforms import PlatformRepository
from app.db.repositories.templates import TemplateRepository
from app.models.agent import Agent
from app.models.app_setting import AppSetting
from app.models.design_system import DesignSystem
from app.models.font import Font
from app.models.platform import Platform
from app.models.template import Template

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Ordered so templates (which reference design_system_id) follow design systems.
TABLES = [
    "design_systems",
    "templates",
    "platforms",
    "fonts",
    "agents",
    "app_settings",
]

# Table name → primary-key column (used to upsert by identity).
PK_COLUMNS = {
    "design_systems": "id",
    "templates": "id",
    "platforms": "id",
    "fonts": "family",
    "agents": "name",
    "app_settings": "key",
}

_MODELS: dict[str, type[DeclarativeBase]] = {
    "design_systems": DesignSystem,
    "templates": Template,
    "platforms": Platform,
    "fonts": Font,
    "agents": Agent,
    "app_settings": AppSetting,
}


def _to_dicts(rows: list) -> list[dict]:
    """Serialize SQLAlchemy model instances to plain dicts (JSON-safe)."""
    out = []
    for row in rows:
        data = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        for k, v in list(data.items()):
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        out.append(data)
    return out


async def _export_rows(session: AsyncSession, model: type[DeclarativeBase]) -> list[dict]:
    res = await session.execute(select(model))
    return _to_dicts(list(res.scalars().all()))


async def export_system(pool) -> dict:
    """Snapshot every config table into one JSON-serializable document."""
    async with pool() as session:
        data = {
            name: await _export_rows(session, model)
            for name, model in _MODELS.items()
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }


def validate_payload(payload: Any) -> list[str]:
    """Return a list of human-readable problems; empty list = valid."""
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            f"unsupported schema_version {payload.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION})"
        )
    for table in TABLES:
        if table not in payload:
            issues.append(f"missing table {table!r}")
        elif not isinstance(payload[table], list):
            issues.append(f"table {table!r} must be a list")
    unknown = sorted(set(payload) - {"schema_version", "exported_at", *TABLES})
    if unknown:
        issues.append(f"unknown top-level keys: {', '.join(map(repr, unknown))}")
    return issues


async def import_system(pool, payload: dict) -> dict:
    """Upsert every config table from an export document.

    Design systems are imported before templates (templates reference
    design_system_id). Rows absent from the payload are left untouched.

    In-process caches (platforms, fonts, agents, runtime settings) are
    refreshed so the Studio and pipeline see the imported values immediately.
    """
    counts: dict[str, int] = {}
    async with pool() as session:
        for table in TABLES:
            rows = payload.get(table) or []
            counts[table] = await _upsert_rows(session, table, rows)
    await _refresh_caches(pool)
    return counts


async def _refresh_caches(pool) -> None:
    """Drop/refresh warm caches so imported rows are visible immediately."""
    try:
        from app.services import platforms as platform_service

        await platform_service.refresh_platforms(pool)
    except Exception as e:  # noqa: BLE001
        log.warning("[system-import] platform cache refresh failed: %s", e)
    try:
        from app.services import fonts as font_service

        await font_service.refresh_font_pool(pool)
    except Exception as e:  # noqa: BLE001
        log.warning("[system-import] font cache refresh failed: %s", e)
    try:
        from app.services import settings as settings_service

        settings_service.invalidate_runtime_settings()
        await settings_service.refresh_runtime_settings(pool)
    except Exception as e:  # noqa: BLE001
        log.warning("[system-import] settings cache refresh failed: %s", e)
    try:
        from app.services import agents as agent_service

        agent_service.invalidate_agent_config()
    except Exception as e:  # noqa: BLE001
        log.warning("[system-import] agent cache refresh failed: %s", e)


async def _upsert_rows(session: AsyncSession, table: str, rows: list[dict]) -> int:
    pk = PK_COLUMNS[table]
    repo = _repo_for(session, table)
    updated = 0
    for row in rows:
        if not isinstance(row, dict) or not row.get(pk):
            log.warning("[system-import] skipping malformed %s row: %r", table, row)
            continue
        key = str(row[pk])
        if await _get(repo, key) is not None:
            await _update(repo, key, row, pk)
        else:
            await _create(repo, key, row, pk)
        updated += 1
    return updated


def _repo_for(session: AsyncSession, table: str):
    repos = {
        "design_systems": DesignSystemRepository,
        "templates": TemplateRepository,
        "platforms": PlatformRepository,
        "fonts": FontRepository,
        "agents": AgentRepository,
        "app_settings": AppSettingRepository,
    }
    return repos[table](session)


async def _get(repo, key: str):
    for method in ("get_by_id", "get_by_name", "get_by_family", "get"):
        fn = getattr(repo, method, None)
        if fn is not None:
            return await fn(key)
    return None


def _clean_row(row: dict) -> dict:
    """Drop timestamp keys that must not be overwritten on upsert.

    created_at/updated_at stay DB-owned (defaults/onupdate apply on create,
    existing values are preserved on update).
    """
    data = dict(row)
    data.pop("created_at", None)
    data.pop("updated_at", None)
    return data


async def _update(repo, key: str, row: dict, pk: str) -> None:
    data = _clean_row(row)
    data.pop(pk, None)
    if isinstance(repo, AppSettingRepository):
        await repo.update(key, data.get("value"), data.get("description"))
    else:
        await repo.update(key, data)


async def _create(repo, key: str, row: dict, pk: str) -> None:
    data = _clean_row(row)
    if isinstance(repo, (DesignSystemRepository, AgentRepository)):
        data.pop(pk, None)
        await repo.create(key, data)
    elif isinstance(repo, AppSettingRepository):
        await repo.create(key, data.get("value"), data.get("description", ""))
    else:
        # Template/Platform/Font repos take the full row (PK included).
        await repo.create(data)
