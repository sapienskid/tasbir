"""Retention sweep — removes expired output artifacts and task records.

Runs on a Celery beat schedule. Anything older than ``OUTPUT_TTL_HOURS`` is
deleted from disk, and the matching SQLite rows are purged so the DB cannot
grow without bound.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete

from app.config import get_settings
from app.db.session import get_shared_session_factory
from app.models.task import GenerationTask
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="retention.sweep_expired")
def sweep_expired() -> None:
    settings = get_settings()
    ttl = timedelta(hours=max(1, settings.output_ttl_hours))
    now = time.time()

    expired_ids: list[str] = []
    output_dir = Path(settings.output_dir)
    if output_dir.is_dir():
        for d in output_dir.iterdir():
            if not d.is_dir():
                continue
            try:
                if now - d.stat().st_mtime > ttl.total_seconds():
                    shutil.rmtree(d, ignore_errors=True)
                    expired_ids.append(d.name)
                    log.info("[retention] Removed expired output %s", d)
            except OSError as e:
                log.warning("[retention] Could not stat/remove %s: %s", d, e)

    async def _purge_db() -> None:
        cutoff = datetime.now(timezone.utc) - ttl
        pool = await get_shared_session_factory()
        async with pool() as session:
            result = await session.execute(
                delete(GenerationTask).where(GenerationTask.updated_at < cutoff)
            )
            await session.commit()
            if result.rowcount:
                log.info("[retention] Purged %d expired task record(s)", result.rowcount)

    if expired_ids:
        asyncio.run(_purge_db())
