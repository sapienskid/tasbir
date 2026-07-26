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

## Parallel Agentic Pipeline Architecture

Tasbir uses a multi-agent design studio workflow built on **LangGraph**. After content strategy analysis, copywriting and art direction execute in **parallel** fan-out, followed by HTML visual graphic design, design quality audit, and parallel rendering:

```
User / Ghost CMS → FastAPI → Celery Worker → LangGraph Parallel Agent Pipeline
                                                    │
                                           ┌────────┴────────┐
                                           │   Strategist    │
                                           │  (Aura Vance)   │
                                           └────────┬────────┘
                                                    │
                               ┌────────────────────┴────────────────────┐
                               ▼                                         ▼
                        Copywriter                                Visual Director
                     (Julian Sterling)                            (Elena Rostova)
                     [Parallel per-format]                        [Parallel per-format]
                               │                                         │
                               └────────────────────┬────────────────────┘
                                                    ▼
                                                 Designer
                                              (Marcus Chen)
                                          [Parallel per-format]
                                                    ▼
                                              Quality Check
                                            (Victoria Thorne)
                                             ┌──────┴──────┐
                                             ▼ (Passed)    ▼ (Failed, retry <=2)
                                          Renderer      Designer
                                       (Playwright PNG)
                                             │
                                             ▼
                                       MinIO Storage
```

### Studio Agent Team Personas

1. **Strategist (Aura Vance)** — Analyzes content narrative, target audience intent, emotional hooks, and synthesizes a master Strategic Brief.
2. **Copywriter (Julian Sterling)** — Crafts platform-tailored, visually structured copy (Headline, Hook, Highlights, Badge Tag, CTA). Strict no-emoji rule.
3. **Visual Director (Elena Rostova)** — Directs background aesthetics, CSS mesh gradients, glassmorphic glows, or selects Unsplash stock photography using tool calls.
4. **Designer (Marcus Chen)** — Generates standalone HTML visual graphic posters using Tailwind CSS, Instrument Serif & Inter fonts, glass cards, and high-contrast typography.
5. **Quality Check (Victoria Thorne)** — Audits generated HTML for canvas constraints, contrast ratios, and placeholder hygiene.
6. **Token Generator (Dr. Soren Lindqvist)** — Translates brand descriptions into W3C DTCG-compliant design tokens.

## Key System Features

* **Zero API Costs**: Runs on Google Gemini free tier, CSS gradients, SVG patterns, and Unsplash free tier.
* **Parallel Execution**: LangGraph fan-out for parallel copywriter & visual director nodes + `asyncio.gather()` format concurrency.
* **Dynamic Database Formats**: Loads user-created formats (`name`, `width`, `height`, `ai_instruction`) dynamically from PostgreSQL.
* **Post-Processing Cleanup**: Automated emoji stripping (`remove_emojis()`) and transformation of website UI button artifacts into non-interactive callouts.
* **Prompt Registry & UI Editing**: Database-backed system prompts with version history editable directly from the UI (**Configure → Prompts**).

## Services

| Service | URL | Description |
|---|---|---|
| API | http://localhost:8000 | FastAPI backend |
| API docs | http://localhost:8000/docs | OpenAPI/Swagger |
| UI | http://localhost:5173 | SvelteKit dashboard |
| MinIO Console | http://localhost:9001 | Asset storage admin |
| Penpot | http://localhost:9001 | Design tool *(add `--profile design`)* |

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

## Stack

- **Backend**: Python 3.12+ (FastAPI, LangGraph, Celery, SQLAlchemy, Playwright)
- **Frontend**: SvelteKit 2 + shadcn-svelte + Tailwind CSS v4
- **Infra**: Docker Compose (PostgreSQL 16, Redis 7, MinIO, Caddy)
- **AI**: Google Gemini 2.0 Flash (free tier, unlimited)
- **Design**: Penpot (self-hosted, open source)
