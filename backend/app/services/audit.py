"""Audit log helper — records per-agent step outcomes for the task trace.

The ``audit_logs`` table existed since v1 but was never written. Nodes now
call ``record_audit()`` at each step (strategist, copywriter, and every
per-format step in the chain) so the task detail UI can show a per-agent
timeline with decision + critique. Best-effort: a DB hiccup never fails the
pipeline.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def record_audit(
    task_id: str,
    agent_name: str,
    decision: dict | None = None,
    critique: str | None = None,
) -> None:
    """Persist one AuditLog row. Never raises."""
    try:
        from app.db.repositories.audit_logs import AuditLogRepository
        from app.db.session import get_shared_session_factory

        pool = await get_shared_session_factory()
        async with pool() as session:
            await AuditLogRepository(session).create(
                task_id=task_id,
                agent_name=agent_name,
                decision=decision or {},
                critique=critique or "",
            )
    except Exception as e:  # noqa: BLE001
        log.warning("[audit] failed to record %s/%s: %s", task_id, agent_name, e)
