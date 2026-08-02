"""Agent jobs API — poll background template/design-system jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.core.time import iso_utc
from app.db.repositories.agent_jobs import AgentJobRepository

router = APIRouter()


@router.get("/{job_id}")
async def get_agent_job(job_id: str, db: AsyncSession = Depends(get_db)):
    repo = AgentJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "created_at": iso_utc(job.created_at),
        "updated_at": iso_utc(job.updated_at),
    }
