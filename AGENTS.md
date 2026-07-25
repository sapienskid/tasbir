# Tasbir v2 — Agent Guide

This file tells AI coding agents everything they need to work on this project.
Read this first before making any changes.

## Project Identity

- **Name**: Tasbir ("depiction" in Arabic)
- **Purpose**: AI-powered social media asset generation pipeline
- **Stack**: Python (FastAPI, LangGraph, Celery) + SvelteKit + Docker
- **Cost target**: Zero API costs (Gemini free tier + CSS backgrounds + Unsplash)

## Architecture Overview

```
User/Ghost → FastAPI API → Celery Task Queue → LangGraph Agent Pipeline
                                                    │
                      ┌─────────────────────────────┼──────────────────┐
                      ▼                             ▼                  ▼
                 Strategist                    Copywriter        Visual Director
                 (content analysis)            (copy gen)        (background choice)
                      │                             │                  │
                      └─────────────────────────────┼──────────────────┘
                                                    ▼
                                              Designer Agent
                                              (HTML + Tailwind)
                                                    │
                                              Quality Agent
                                              (validation)
                                                    │
                                              Playwright Render
                                              (HTML → PNG)
                                                    │
                                              MinIO Storage
```

## Directory Structure

```
tasbir/
├── PLAN.md                  ← Project plan & phases (CONSULT THIS FIRST)
├── AGENTS.md                ← This file — agent instructions
├── DESIGN.md                ← Architecture & design decisions
├── docker-compose.yml       ← All services orchestrated
├── .env.example             ← Required environment variables
│
├── backend/                 ← Python FastAPI backend
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── alembic.ini
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             ← FastAPI app entry point
│   │   ├── config.py           ← Pydantic Settings (env-based)
│   │   │
│   │   ├── api/                ← FastAPI route modules
│   │   │   ├── __init__.py
│   │   │   ├── health.py       ← GET /health
│   │   │   ├── settings.py     ← CRUD /settings
│   │   │   ├── templates.py    ← CRUD /templates
│   │   │   ├── tokens.py       ← CRUD /tokens + generate
│   │   │   ├── formats.py      ← CRUD /formats
│   │   │   ├── generate.py     ← POST /generate (SSE stream)
│   │   │   ├── tasks.py        ← GET /tasks/{id}
│   │   │   ├── assets.py       ← GET /assets/{key}
│   │   │   ├── prompts.py      ← CRUD /prompts (registry)
│   │   │   └── webhooks/       ← Ghost + Penpot webhooks
│   │   │       ├── __init__.py
│   │   │       ├── ghost.py
│   │   │       └── penpot.py
│   │   │
│   │   ├── models/             ← SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── settings.py
│   │   │   ├── template.py
│   │   │   ├── task.py
│   │   │   ├── asset.py
│   │   │   ├── prompt.py
│   │   │   ├── tokens.py
│   │   │   └── format.py
│   │   │
│   │   ├── agents/             ← LangGraph agent definitions
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── graph.py         ← State machine definition
│   │   │   │   ├── state.py         ← GenerationState TypedDict
│   │   │   │   ├── nodes/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── strategist.py
│   │   │   │   │   ├── copywriter.py
│   │   │   │   │   ├── visual_director.py
│   │   │   │   │   ├── designer.py
│   │   │   │   │   └── quality_check.py
│   │   │   │   └── tools/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── search_templates.py
│   │   │   │       ├── search_unsplash.py
│   │   │   │       ├── generate_background.py
│   │   │   │       ├── fetch_design_tokens.py
│   │   │   │       └── render_preview.py
│   │   │   │
│   │   │   └── prompts/         ← Default prompt templates
│   │   │       ├── __init__.py
│   │   │       ├── registry.py  ← Prompt loading + versioning
│   │   │       ├── strategist.py
│   │   │       ├── copywriter.py
│   │   │       ├── visual_director.py
│   │   │       ├── designer.py
│   │   │       └── quality_check.py
│   │   │
│   │   ├── services/            ← Business logic
│   │   │   ├── __init__.py
│   │   │   ├── llm.py           ← Gemini/LLM client
│   │   │   ├── backgrounds.py   ← CSS gradient + SVG pattern generator
│   │   │   ├── unsplash.py      ← Free stock photo client
│   │   │   ├── renderer.py      ← Playwright render client
│   │   │   ├── storage.py       ← MinIO/S3 client
│   │   │   ├── penpot.py        ← Penpot MCP client
│   │   │   ├── token_exchange.py ← DTCG ↔ internal format
│   │   │   ├── token_sync.py    ← Penpot ↔ DB sync
│   │   │   └── ghost.py         ← Ghost Admin API client
│   │   │
│   │   ├── core/                ← Shared infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── security.py      ← API key auth + rate limiting
│   │   │   ├── errors.py        ← HTTP exceptions
│   │   │   ├── logging.py       ← Structured logging
│   │   │   └── dependencies.py  ← FastAPI dependency injection
│   │   │
│   │   ├── db/                  ← Database layer
│   │   │   ├── __init__.py
│   │   │   ├── session.py       ← SQLAlchemy async engine
│   │   │   ├── migrations/      ← Alembic migrations
│   │   │   └── repositories/    ← Data access layer
│   │   │       ├── __init__.py
│   │   │       ├── settings.py
│   │   │       ├── templates.py
│   │   │       ├── tasks.py
│   │   │       ├── assets.py
│   │   │       └── prompts.py
│   │   │
│   │   └── tasks/               ← Celery task definitions
│   │       ├── __init__.py
│   │       ├── celery_app.py    ← Celery app configuration
│   │       └── generate.py      ← Main generation task
│   │
│   └── tests/                   ← pytest tests
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_api/
│       ├── test_agents/
│       └── test_services/
│
├── ui/                          ← SvelteKit frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── components.json          ← shadcn-svelte config
│   │
│   ├── src/
│   │   ├── app.html
│   │   ├── app.css
│   │   │
│   │   ├── routes/              ← SvelteKit pages
│   │   │   ├── +page.svelte     ← Dashboard (pipeline hero, stats, tasks)
│   │   │   ├── +layout.svelte   ← Sidebar (5 items: Dashboard, Create, Assets, Templates, Configure)
│   │   │   ├── create/
│   │   │   │   └── +page.svelte ← Create assets (two-column form, result grid)
│   │   │   ├── assets/
│   │   │   │   └── +page.svelte ← Asset gallery grouped by generation
│   │   │   ├── templates/
│   │   │   │   └── +page.svelte ← HTML template CRUD
│   │   │   ├── configure/
│   │   │   │   ├── +page.svelte ← Tabbed: General, Brand, Formats, Prompts
│   │   │   │   └── ghost-webhook/
│   │   │   │       └── +page.svelte ← Ghost webhook setup guide
│   │   │   ├── tasks/
│   │   │   │   ├── +page.svelte ← Task list with cancel/retry
│   │   │   │   └── [id]/
│   │   │   │       └── +page.svelte ← Task detail with SSE
│   │   │   ├── generate/        ← Redirects to /create
│   │   │   ├── settings/        ← Redirects to /configure
│   │   │   ├── tokens/          ← Redirects to /configure
│   │   │   ├── formats/         ← Redirects to /configure
│   │   │   ├── prompts/         ← Redirects to /configure
│   │   │   └── brand/           ← Redirects to /configure
│   │   │
│   │   └── lib/
│   │       ├── actions/         ← Svelte actions
│   │       │   └── clickOutside.svelte.ts
│   │       ├── api/             ← Typed API client
│   │       │   ├── client.ts
│   │       │   ├── settings.ts
│   │       │   ├── templates.ts
│   │       │   ├── tokens.ts
│   │       │   ├── formats.ts
│   │       │   └── generate.ts
│   │       ├── components/      ← Svelte components
│   │       │   ├── TokenPreview.svelte  ← Visual token renderer
│   │       │   └── ui/          ← shadcn-svelte components (CLI-installed)
│   │       │       ├── button/          ← Button + variants
│   │       │       ├── card/            ← Card + CardHeader/Title/Description/Footer
│   │       │       ├── input/           ← Input
│   │       │       ├── select/          ← Select (bits-ui based, fully custom dropdown)
│   │       │       ├── dialog/          ← Dialog + DialogContent/Header/Title/Description
│   │       │       ├── separator/       ← Separator
│   │       │       └── confirm.svelte   ← Thin wrapper around Dialog for confirmations
│   │       └── stores/          ← Svelte stores
│   │           ├── auth.ts
│   │           ├── tasks.ts
│   │           └── settings.ts
│   │
│   └── static/
│       └── favicon.svg
│
├── scripts/
│   ├── seed.py                  ← Seed default data
│   └── migrate.sh               ← Run Alembic migrations
│
└── docker/
    ├── Dockerfile.api
    ├── Dockerfile.worker
    └── Dockerfile.ui
```

## Tech Stack Reference

### Backend

| Technology | Purpose | Package |
|---|---|---|
| FastAPI | HTTP API framework | `fastapi` |
| SQLAlchemy 2.0 | ORM (async) | `sqlalchemy[asyncio]` |
| Alembic | DB migrations | `alembic` |
| Celery | Task queue | `celery[redis]` |
| LangGraph | Agent state machine | `langgraph` |
| LiteLLM | Multi-provider AI | `litellm` |
| google-generativeai | Gemini free tier | `google-genai` |
| Playwright | Browser rendering | `playwright` |
| httpx | Async HTTP client | `httpx` |
| Pydantic v2 | Validation + settings | `pydantic` |
| MinIO client | S3 object storage | `minio` |
| pytest | Testing | `pytest` |

### Frontend

| Technology | Purpose | Package |
|---|---|---|
| SvelteKit | Meta-framework | `create-svelte` |
| shadcn-svelte | UI components (CLI) | `shadcn-svelte` |
| Tailwind CSS v4 | Utility CSS | `tailwindcss` |
| bits-ui | Headless UI primitives | `bits-ui` |
| lucide-svelte | Icons (sidebar) | `lucide-svelte` |
| @lucide/svelte | Icons (shadcn components) | `@lucide/svelte` |

### Design System

| Token | Value |
|---|---|
| Background | `#0A0A0C` |
| Surface | `#141418` |
| Elevated | `#202026` |
| Border | `#2C2C30` |
| Text | `#EEE9E4` |
| Accent | `#CD5B7D` (dusty rose) |
| Secondary | `#5B7D7C` |
| Destructive | `#B05E5E` |
| Display font | Instrument Serif |
| Body font | Inter |
| Mono font | JetBrains Mono |

## Coding Standards

### Python

- Always use `async/await` (FastAPI is async-first)
- Always use type hints (Pydantic + mypy)
- Use `Path` from `pathlib`, not `os.path`
- Services are stateless classes or module-level async functions
- Agents are LangGraph `StateGraph` nodes
- Database access through repository pattern
- All prompts stored in `prompt_registry` table, not hardcoded
- Pydantic models for all API schemas (no dicts)

### TypeScript/Svelte

- Strict TypeScript mode
- Components use `$props()` rune for props
- Stores use `$state()` rune
- API calls through typed client in `$lib/api/`
- shadcn-svelte components go in `$lib/components/ui/`
- One component per file

### Git

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, etc.
- One commit per logical change
- Don't commit secrets or generated files

## Environment Variables

All configuration through environment variables (see `.env.example`).
Required vars have no default and will fail at startup if missing.

### LLM Configuration
`GEMINI_API_KEY` — Google AI Studio API key (free tier)
`OPENROUTER_API_KEY` — Optional fallback

### Storage
`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` — MinIO credentials
`MINIO_BUCKET` — Asset bucket name (default: `tasbir-assets`)

### Database
`DATABASE_URL` — PostgreSQL connection string

### Ghost CMS
`GHOST_ADMIN_API_KEY` — Admin API key (format: `id:secret`)
`GHOST_URL` — Ghost instance URL
`GHOST_WEBHOOK_SECRET` — Webhook signature secret

### Penpot
`PENPOT_URL` — Penpot instance URL
`PENPOT_ACCESS_TOKEN` — Penpat API access token

### Unsplash
`UNSPLASH_ACCESS_KEY` — Unsplash API key (free tier)

## Common Tasks For AI Agents

### Adding a new API endpoint
1. Create route in `backend/app/api/`
2. Create request/response models in `backend/app/models/` (if new)
3. Add repository methods if new DB access needed
4. Register router in `backend/app/main.py`
5. Add test in `backend/tests/test_api/`

### Adding a new agent node
1. Create node in `backend/app/agents/orchestrator/nodes/`
2. Add prompt to `backend/app/agents/prompts/`
3. Register prompt in `prompt_registry.py`
4. Add node to `orchestrator/graph.py`
5. Update `GenerationState` in `state.py` if new state fields needed

### Adding a new tool for agents
1. Create tool function in `backend/app/agents/orchestrator/tools/`
2. Decorate with LangGraph `@tool`
3. Register in `orchestrator/tools/__init__.py`
4. Add to the relevant agent node's tool list

### Adding a new frontend page
1. Create route in `ui/src/routes/`
2. Add API methods in `ui/src/lib/api/`
3. Create page component
4. Add navigation link in `+layout.svelte` sidebar
5. If the old route path is changing, add a redirect page

## Testing

- Backend: `cd backend && pytest` (uses pytest-asyncio)
- Frontend: `cd ui && vitest run`
- Tests should not require external services (mock LLM, Playwright, etc.)

## Troubleshooting

- **Gemini free tier exhausted**: Wait for next day or add `OPENROUTER_API_KEY`
- **Playwright fails**: Check Chromium installation `playwright install chromium`
- **Celery tasks stuck**: Check Redis connection, restart worker
- **Penpot connection fails**: Verify `PENPOT_ACCESS_TOKEN` and `PENPOT_URL`
- **Database migrations**: `cd backend && alembic upgrade head`
