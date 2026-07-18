# Tasbir v2

AI-powered social media asset generation pipeline. Zero API costs.
Self-hosted via Docker.

> **For AI agents**: Read [AGENTS.md](AGENTS.md) before making changes.
> **For project plan**: See [PLAN.md](PLAN.md).
> **For architecture**: See [DESIGN.md](DESIGN.md).

## Quick Start

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY (free from aistudio.google.com)
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python ../scripts/seed.py
```

Open http://localhost:5173 for the UI, or http://localhost:8000/docs for the API.

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env   # Edit with your keys
uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
python -m pytest
```

### Frontend

```bash
cd ui
npm install
npm run dev        # dev server at :5173
npm test           # vitest
npm run build      # production build
```

### Database

```bash
# Run migrations
cd backend
alembic upgrade head

# Seed default formats, prompts, settings
python ../scripts/seed.py

# Create a new migration
alembic revision --autogenerate -m "description"
```

## Services

| Service | URL | Description |
|---|---|---|
| API | http://localhost:8000 | FastAPI backend |
| API docs | http://localhost:8000/docs | OpenAPI/Swagger |
| UI | http://localhost:5173 | SvelteKit dashboard |
| MinIO Console | http://localhost:9001 | Asset storage admin |
| Penpot | http://localhost:9001 | Design tool *(add `--profile design`)* |

## Architecture

```
User → FastAPI → Celery Worker → LangGraph Pipeline
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Strategist       Copywriter      Visual Director
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                              Designer
                              (HTML + Tailwind)
                                    ▼
                              Quality Check
                               ┌────┴────┐
                               ▼         ▼
                          Renderer    Designer
                          (PNG)      (retry max 2)
                               ▼
                             MinIO
```

### Agent Pipeline

The pipeline has 6 nodes:

1. **Strategist** — analyzes content, produces a strategic brief
2. **Copywriter** — generates per-format copy text
3. **Visual Director** — chooses backgrounds (CSS gradients, patterns, or Unsplash photos) using `bind_tools()` so the model decides which tool to call
4. **Designer** — generates HTML with Tailwind CSS, optionally searches templates and fetches design tokens
5. **Quality Check** — validates output, can loop back to Designer for refinements
6. **Renderer** — deterministic step that converts HTML → PNG via Playwright and uploads to MinIO

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key (free tier) |
| `OPENROUTER_API_KEY` | No | — | Fallback LLM provider |
| `DATABASE_URL` | No | `postgresql+asyncpg://tasbir:tasbir@postgres:5432/tasbir` | PostgreSQL |
| `REDIS_URL` | No | `redis://redis:6379/0` | Celery broker |
| `GHOST_URL` | No | — | Ghost CMS instance URL |
| `GHOST_ADMIN_API_KEY` | No | — | Ghost Admin API key |
| `PENPOT_URL` | No | `http://localhost:9001` | Penpot instance |
| `UNSPLASH_ACCESS_KEY` | No | — | Unsplash API key |
| `API_KEYS` | No | — | Comma-separated keys for API auth |

## Stack

- **Backend**: Python 3.12+ (FastAPI, LangGraph, Celery, SQLAlchemy, Playwright)
- **Frontend**: SvelteKit 2 + shadcn-svelte + Tailwind CSS v4
- **Infra**: Docker Compose (PostgreSQL 16, Redis 7, MinIO, Caddy)
- **AI**: Google Gemini 2.0 Flash (free tier, unlimited)
- **Design**: Penpot (self-hosted, open source)

## Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY` missing | Set it in `.env`. Get a free key at https://aistudio.google.com/app/apikey |
| Celery tasks stuck | Check Redis is running: `docker compose ps redis` |
| Playwright render fails | Check Playwright container: `docker compose ps playwright` |
| Database migration errors | Run `cd backend && alembic upgrade head` |
| Penpot connection fails | Verify `PENPOT_URL` and `PENPOT_ACCESS_TOKEN` in `.env` |
| Port conflict on 9001 | Penpot and MinIO both use 9001. Use `--profile design` for Penpot to avoid conflict |
