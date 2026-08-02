import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import (
    agent_jobs,
    design_systems,
    generate,
    health,
    tasks,
    templates,
    uploads,
)
from app.config import get_settings
from app.core.ratelimit import close_redis, rate_limiter
from app.core.security import verify_api_key

log = logging.getLogger(__name__)

# Optional built frontend (Tasbir Studio) — served when present.
_STATIC_DIR = Path("/app/static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import close_shared_engine, get_shared_session_factory
    from app.models import Base

    pool = await get_shared_session_factory()
    app.state.pool = pool

    # Create SQLite tables if they don't exist yet
    from sqlalchemy.ext.asyncio import create_async_engine
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    log.info("[startup] SQLite tables created/verified")

    # Seed the default design system + template library (idempotent).
    try:
        from app.services.seeding import seed_default_design_system
        await seed_default_design_system(pool)
    except Exception as e:
        log.warning("[startup] Design system seed failed: %s", e)

    yield
    await close_shared_engine()
    await close_redis()


settings = get_settings()

app = FastAPI(
    title="Tasbir API",
    version="0.5.0",
    description="AI-powered social media asset pipeline — HTML + PNG output",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public
app.include_router(health.router, tags=["health"])

# Protected (under /api so the SPA routes — /, /new, /templates, /design-systems — never collide)
app.include_router(
    generate.router, prefix="/api/generate", tags=["generate"],
    dependencies=[Depends(verify_api_key), Depends(rate_limiter)]
)
app.include_router(
    tasks.router, prefix="/api/tasks", tags=["tasks"],
    dependencies=[Depends(verify_api_key), Depends(rate_limiter)]
)
app.include_router(
    design_systems.router, prefix="/api/design-systems", tags=["design-systems"],
    dependencies=[Depends(verify_api_key), Depends(rate_limiter)]
)
app.include_router(
    templates.router, prefix="/api/templates", tags=["templates"],
    dependencies=[Depends(verify_api_key), Depends(rate_limiter)]
)
app.include_router(
    agent_jobs.router, prefix="/api/agent-jobs", tags=["agent-jobs"],
    dependencies=[Depends(verify_api_key), Depends(rate_limiter)]
)
app.include_router(
    uploads.router, prefix="/api/uploads", tags=["uploads"],
    dependencies=[Depends(verify_api_key), Depends(rate_limiter)]
)


def _has_frontend() -> bool:
    return _STATIC_DIR.is_dir() and any(_STATIC_DIR.iterdir())


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Serve the built SPA (with index.html fallback for client routes)."""
    if not _has_frontend():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if full_path:
        candidate = (_STATIC_DIR / full_path).resolve()
        try:
            candidate.relative_to(_STATIC_DIR.resolve())
        except ValueError:
            candidate = _STATIC_DIR / "index.html"
        if candidate.is_file():
            return FileResponse(candidate)
    index = _STATIC_DIR / "index.html"
    if index.is_file():
        # Never cache index.html — asset filenames are content-hashed, so the
        # browser always gets the latest build on refresh.
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    return JSONResponse({"detail": "Not found"}, status_code=404)
