from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import health, settings as settings_router
from app.api import templates, tokens, formats, generate, tasks, assets, prompts
from app.api.webhooks import ghost as ghost_webhook, penpot as penpot_webhook
from app.core.dependencies import get_db
from app.core.security import verify_api_key
from app.db.session import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine, pool = await create_pool(settings.database_url)
    app.state.pool = pool
    app.state.engine = engine
    yield
    await engine.dispose()


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

# Public routes (no auth required)
app.include_router(health.router, tags=["health"])

# Protected routes (API key required if configured)
app.include_router(settings_router.router, prefix="/settings", tags=["settings"], dependencies=[Depends(verify_api_key)])
app.include_router(templates.router, prefix="/templates", tags=["templates"], dependencies=[Depends(verify_api_key)])
app.include_router(tokens.router, prefix="/tokens", tags=["tokens"], dependencies=[Depends(verify_api_key)])
app.include_router(formats.router, prefix="/formats", tags=["formats"], dependencies=[Depends(verify_api_key)])
app.include_router(generate.router, prefix="/generate", tags=["generate"], dependencies=[Depends(verify_api_key)])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"], dependencies=[Depends(verify_api_key)])
app.include_router(assets.router, prefix="/assets", tags=["assets"], dependencies=[Depends(verify_api_key)])
app.include_router(prompts.router, prefix="/prompts", tags=["prompts"], dependencies=[Depends(verify_api_key)])
app.include_router(ghost_webhook.router, prefix="/webhooks", tags=["webhooks"], dependencies=[Depends(verify_api_key)])
app.include_router(penpot_webhook.router, prefix="/webhooks", tags=["webhooks"], dependencies=[Depends(verify_api_key)])
