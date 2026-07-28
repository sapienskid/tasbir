from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import health, generate, tasks
from app.core.security import verify_api_key

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import get_shared_session_factory, close_shared_engine
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

    yield
    await close_shared_engine()


settings = get_settings()

app = FastAPI(
    title="Tasbir API",
    version="0.3.0",
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

# Protected
app.include_router(
    generate.router, prefix="/generate", tags=["generate"],
    dependencies=[Depends(verify_api_key)]
)
app.include_router(
    tasks.router, prefix="/tasks", tags=["tasks"],
    dependencies=[Depends(verify_api_key)]
)
