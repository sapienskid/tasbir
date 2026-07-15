from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import health, settings as settings_router
from app.db.session import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.pool = await create_pool(settings.database_url)
    yield
    await app.state.pool.close()


settings = get_settings()

app = FastAPI(
    title="Tasbir API",
    version="0.2.0",
    description="AI-powered social media asset generation pipeline",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(settings_router.router, prefix="/settings", tags=["settings"])


@app.get("/openapi.json", include_in_schema=False)
async def openapi():
    return app.openapi()
