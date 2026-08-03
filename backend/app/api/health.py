"""Health check endpoints.

- GET /health        — fast liveness probe (always 200 while the process runs)
- GET /health/ready  — readiness probe: verifies SQLite, Redis, and the
                       Playwright render service. Returns 503 when any
                       dependency is unavailable so orchestrators/healthchecks
                       can distinguish "up" from "ready to serve traffic".
"""

import logging

from fastapi import APIRouter, Response

log = logging.getLogger(__name__)

router = APIRouter()


async def _check_sqlite() -> tuple[bool, str]:
    from sqlalchemy import text

    from app.db.session import get_shared_session_factory

    try:
        pool = await get_shared_session_factory()
        async with pool() as session:
            await session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        log.warning("[health] SQLite check failed: %s", e)
        return False, str(e)


async def _check_redis() -> tuple[bool, str]:
    from app.core.ratelimit import _get_redis

    try:
        redis = await _get_redis()
        await redis.ping()
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        log.warning("[health] Redis check failed: %s", e)
        return False, str(e)


async def _check_render() -> tuple[bool, str]:
    import httpx

    from app.config import get_settings

    settings = get_settings()
    renderer_url = settings.renderer_url
    if not renderer_url:
        return False, "renderer_url not configured"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{renderer_url}/health")
        ok = r.status_code == 200
        return ok, "" if ok else f"status {r.status_code}"
    except Exception as e:  # noqa: BLE001
        log.warning("[health] Render check failed: %s", e)
        return False, str(e)


@router.get("/health")
async def health():
    from app.config import get_settings

    settings = get_settings()
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "tasbir",
        "llm_configured": bool(settings.gemini_api_key),
    }


@router.get("/health/ready")
async def health_ready(response: Response):
    checks = {
        "sqlite": await _check_sqlite(),
        "redis": await _check_redis(),
        "render": await _check_render(),
    }
    ready = all(ok for ok, _ in checks.values())
    response.status_code = 200 if ready else 503
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {name: {"ok": ok, "detail": detail} for name, (ok, detail) in checks.items()},
    }
