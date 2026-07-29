# Tasbir v3

AI-powered social media asset pipeline. Blog content goes in,
platform-optimized HTML + PNG renders come out. Zero API costs.
Self-hosted via Docker.

> **For AI agents**: Read [AGENTS.md](AGENTS.md) before making changes.
> **For project plan**: See [PLAN.md](PLAN.md).
> **For architecture**: See [DESIGN.md](DESIGN.md).

## Quick Start

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY (free from aistudio.google.com)
docker compose up -d
```

Open http://localhost:8000/docs for the API.

## Architecture

```
n8n/Webhook → FastAPI → Celery + Redis → LangGraph Pipeline → HTML + PNG
                                                         │
                                                  Designer creates HTML
                                                  Verifier renders to PNG
                                                  via Playwright
```

### Pipeline (4 agents)

Strategist → Copywriter → Designer → Verifier

Each agent outputs typed JSON (Pydantic). Design tokens live in YAML files —
the LLM never sees brand colors or hex values.

### Agent Team

1. **Strategist** (Aura Vance) — content analysis → structured brief
2. **Copywriter** (Julian Sterling) — per-platform copy (headline, subhead, body)
3. **Designer** (Marcus Chen) — HTML with CSS variables (`var(--color-*)`)
4. **Verifier** (Victoria Thorne) — injects tokens/KateX/images, renders to PNG,
   multimodal audit via Gemini Vision

## Services

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | FastAPI (trigger generation, task status) |
| API docs | http://localhost:8000/docs | OpenAPI/Swagger |
| Playwright | http://localhost:4000 | Headless Chromium (HTML render + DOM extraction) |

## Development

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

## Stack

- **Backend**: Python 3.12+ (FastAPI, LangGraph, Celery, Playwright)
- **Rendering**: Playwright (headless Chromium, Docker)
- **Queue**: Celery + Redis
- **Storage**: SQLite (tasks) + `data/output/{task_id}/` (HTML, PNG)
- **AI**: Gemini 3.5 Flash Lite (free tier)
- **Config**: YAML (brand, tokens, platforms, campaigns)
