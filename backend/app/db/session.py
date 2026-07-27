"""Shared async DB engine factory — SQLite via aiosqlite.

Provides a single module-level engine + session factory that is reused
across all agent nodes and services within the same process.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

log = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_lock = asyncio.Lock()


async def get_shared_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory

    if _session_factory is not None:
        return _session_factory

    async with _lock:
        if _session_factory is not None:
            return _session_factory

        from app.config import get_settings

        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
        )
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        log.info("[db.shared] Shared async DB engine initialised (SQLite)")

    return _session_factory


async def close_shared_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("[db.shared] Shared async DB engine disposed")
