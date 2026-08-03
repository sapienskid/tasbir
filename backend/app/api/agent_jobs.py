"""Agent jobs API — task-based template/brand jobs.

- GET    /agent-jobs            list (Tasks-page integration)
- GET    /agent-jobs/{job_id}   poll one job
- DELETE /agent-jobs/{job_id}   remove a job
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.core.time import iso_utc
from app.db.repositories.agent_jobs import AgentJobRepository

router = APIRouter()

MAX_LIST = 100


def _job_dict(row) -> dict:
    result = row.result or {}
    title = ""
    if row.kind == "design_system":
        title = result.get("design_system_id") or "Brand builder job"
    elif row.kind == "template":
        title = result.get("template_id") or "Template job"
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "result": result,
        "error": row.error,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
        "title": title,
    }


@router.get("")
async def list_agent_jobs(
    kind: str | None = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    repo = AgentJobRepository(db)
    jobs = await repo.list_recent(min(MAX_LIST, max(1, limit)), kind)
    return [_job_dict(j) for j in jobs]


@router.get("/{job_id}")
async def get_agent_job(job_id: str, db: AsyncSession = Depends(get_db)):
    repo = AgentJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    return _job_dict(job)


@router.delete("/{job_id}")
async def delete_agent_job(job_id: str, db: AsyncSession = Depends(get_db)):
    repo = AgentJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    await repo.delete(job_id)
    return {"deleted": job_id}