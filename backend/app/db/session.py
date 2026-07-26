"""Shared async DB engine factory.

Provides a single module-level engine + session factory that is reused
across all agent nodes and services within the same process.

Using a fresh ``create_pool()`` call per agent node (the old pattern)
created one engine per format per pipeline run, which opened up to 25+
PostgreSQL connections simultaneously for a 5-format job.

This module is initialised lazily on first use and disposed cleanly on
process shutdown (or when ``close_shared_engine()`` is called).
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
    """Return the process-wide session factory, creating it on first call.

    Thread/task-safe: uses an asyncio.Lock so concurrent callers wait
    rather than each spinning up their own engine.
    """
    global _engine, _session_factory

    if _session_factory is not None:
        return _session_factory

    async with _lock:
        # Double-checked locking — another coroutine may have initialised it
        # while we waited for the lock.
        if _session_factory is not None:
            return _session_factory

        from app.config import get_settings
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # detect stale connections
        )
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        log.info("[db.shared] Shared async DB engine initialised")

    return _session_factory


async def close_shared_engine() -> None:
    """Dispose the shared engine — call this during app shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("[db.shared] Shared async DB engine disposed")


# ---------------------------------------------------------------------------
# Legacy helper — kept for backwards compat with code that calls create_pool()
# directly. New code should prefer get_shared_session_factory().
# ---------------------------------------------------------------------------

async def create_pool(database_url: str):  # type: ignore[return]
    """Create a one-off engine + session factory.

    Prefer ``get_shared_session_factory()`` for agent nodes and services
    that are called on every generation run. Use this only for migration
    scripts or isolated one-off operations.
    """
    engine = create_async_engine(database_url, echo=False, pool_size=5)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
