# Tasbir v2

AI-powered social media asset generation pipeline. Zero API costs.
Self-hosted via Docker. No Cloudflare dependencies.

> **For AI agents**: Read [AGENTS.md](AGENTS.md) before making changes.
> **For project plan**: See [PLAN.md](PLAN.md).
> **For architecture**: See [DESIGN.md](DESIGN.md).

## Quick Start

```bash
cp .env.example .env
# Edit .env with your GEMINI_API_KEY (free from aistudio.google.com)
docker compose up -d
```

## Services

| Service | URL | Description |
|---|---|---|
| API | http://localhost:8000 | FastAPI backend |
| UI | http://localhost:5173 | SvelteKit dashboard |
| MinIO | http://localhost:9001 | Asset storage (admin) |
| Penpot | http://localhost:9001 | Design tool *(docker compose --profile design up)* |

## Stack

- **Backend**: Python (FastAPI, LangGraph, Celery, Playwright)
- **Frontend**: SvelteKit + shadcn-svelte + Tailwind CSS
- **Infra**: Docker Compose (PostgreSQL, Redis, MinIO, Caddy)
- **AI**: Google Gemini free tier (zero cost)
- **Design**: Penpot (self-hosted, open source)
