# Tasbir v3

AI-powered social media asset pipeline. Blog content goes in,
platform-optimized HTML + PNG renders come out. Zero API costs.
Self-hosted via Docker.

> **For AI agents**: Read [AGENTS.md](AGENTS.md) before making changes.
> **For project plan**: See [PLAN.md](PLAN.md).
> **For architecture**: See [DESIGN.md](DESIGN.md).
> **For design decisions**: See [docs/adr/](docs/adr/) and [docs/glossary.md](docs/glossary.md).

## Quick Start

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY + API_KEYS (and RENDER_SERVICE_KEY for Docker)
docker compose up -d --build
```

Open http://localhost:8000 — the Tasbir Studio SPA (task list, HTML editor,
PNG preview, re-render, QC) is served by the API itself. API docs at
http://localhost:8000/docs.

## Tasbir Studio

A React + Vite + shadcn/ui SPA served same-origin by FastAPI:
- Task list with status polling and delete
- Per-format Monaco HTML editor + live PNG preview + QC report
- **Re-render** (edit → render → deterministic QC) and **Audit** (opt-in vision QC)
- **Download PNG/HTML** (repeatable until the retention window; `?consume=true` deletes after download)
- API key stored in localStorage (`tasbir:apikey:v1`)

Artifacts are **ephemeral**: they persist until the hourly TTL sweep, and an
hourly sweep removes anything older than `OUTPUT_TTL_HOURS` (default 24h).

## Hot Reload (Development)

```bash
# One-time: set API_KEYS + RENDER_SERVICE_KEY in .env
cp .env.example .env   # then edit

# Live-reload stack: uvicorn --reload (api/playwright),
# watchfiles-restarted celery (worker/beat), Vite dev server (frontend)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# UI at http://localhost:5173 · API at http://localhost:8000
```

The dev overlay bind-mounts `./backend` and `./frontend` into the containers,
so backend code, prompts, YAML design files, and React source all hot-reload.
The Vite dev server proxies `/tasks` + `/generate` to the `api` service.
Stop it with `docker compose -f docker-compose.yml -f docker-compose.dev.yml down`.

For a normal (non-reload) deploy: `docker compose up -d --build`.

## Architecture

```
n8n/Webhook → FastAPI → Celery + Redis → LangGraph Pipeline → HTML + PNG
                                                          │
                                                   Designer creates HTML
                                                   Verifier renders to PNG
                                                   via Playwright
```

### Pipeline

Strategist → Copywriter → process_all_formats (Designer → Renderer → Verifier,
per-format in parallel, with retry loop).

Each agent outputs typed JSON (Pydantic). Design tokens and typography live in
YAML files — the LLM never sees brand colors or hex values.

### Agent Team

1. **Strategist** (Aura Vance) — content analysis → structured brief + category + ground
2. **Copywriter** (Julian Sterling) — per-platform copy (headline, subhead, body)
3. **Designer** (Marcus Chen) — HTML with CSS variables (`var(--color-*)`)
4. **Renderer** — injects tokens/fonts/KaTeX/images, saves HTML
5. **Verifier** (Victoria Thorne) — deterministic checks + renders to PNG +
   multimodal audit via Gemini Vision

The typographic system uses three voices, all config-driven in
`data/design_system/`: Space Grotesk (display — headline + wordmark),
Source Serif 4 (editorial — subhead + body), Inter (interface — category,
metadata, handle).

## Services

| Service | URL | Description |
|---------|-----|-------------|
| API + Studio | http://localhost:8000 | FastAPI + Tasbir Studio SPA (same origin) |
| API docs | http://localhost:8000/docs | OpenAPI/Swagger |
| Playwright | internal (`tasbir` network) | Headless Chromium (render + DOM extraction, key-authed) |

## Production

- Code is baked into the images (`--build` after code changes); config
  (`config/prompts/`) and data (`data/design_system/`, `data/output/`) are
  bind-mounted for config-driven control without rebuilds.
- Dependencies are pinned in `backend/pyproject.toml` and
  `backend/requirements.txt`.
- The SQLite task DB (`backend/data/tasbir.db`) is runtime data — keep it
  out of version control (it's gitignored).

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
- **Frontend**: React 19 + Vite + shadcn/ui + SWR + Monaco (Tasbir Studio)
- **Rendering**: Playwright (headless Chromium, Docker, internal-only)
- **Queue**: Celery + Redis (worker + beat for retention sweep)
- **Storage**: SQLite (tasks) + `data/output/{task_id}/` (HTML, PNG — ephemeral)
- **AI**: Gemini 3.5 Flash Lite (free tier)
- **Config**: YAML (brand, tokens, platforms, campaigns, design-instruction)
