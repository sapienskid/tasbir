# Tasbir v1.0.0

AI-powered social media asset pipeline. Blog content goes in,
platform-optimized HTML + PNG renders come out. Zero API costs.
Self-hosted via Docker.

> **For AI agents**: Read [AGENTS.md](AGENTS.md) before making changes.
> **For project plan**: See [PLAN.md](PLAN.md).
> **For architecture**: See [DESIGN.md](DESIGN.md).
> **For design decisions**: See [docs/adr/](docs/adr/) and [docs/glossary.md](docs/glossary.md).
> **For releases**: See [CHANGELOG.md](CHANGELOG.md).

## Quick Start (Production)

Tasbir publishes its Docker images to **GitHub Container Registry**
(`ghcr.io/sapienskid/tasbir-*`), built automatically by CI on tags (`v*` →
versioned + `:latest`) and pushes to `main` (`:main`). Production deployments
pull these prebuilt images; see [Deploying with Docker](#deploying-with-docker)
below for the full recipe.

## Development

Two ways to run locally — pick whichever you prefer. Both hot-reload.

### Option A — Docker dev stack (recommended)

`docker-compose.dev.yml` builds `api`/`worker`/`beat` from local source with
**hot reload** (uvicorn `--reload` + watchfiles), pulls the heavyweight
`playwright` and `redis` images prebuilt, and serves the Studio via the vite
dev server (HMR):

```bash
cp .env.example .env            # set GEMINI_API_KEY + API_KEYS
docker compose -f docker-compose.dev.yml up --build
```

**URLs (dev):** the UI and API are two separate servers.

| What | URL |
|------|-----|
| Studio UI (vite, HMR) | http://localhost:5173 |
| API (FastAPI) | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

The vite dev server proxies `/api/*` → `api:8000`, so the UI at :5173 talks to
the API transparently. In the dev image the SPA is **not** baked in, so
`:8000` serves the API only (its root shows a pointer page). Production bakes
the SPA into the image, so there `:8000` serves everything.

- `./backend` is bind-mounted at `/app`, so **you own all data**: seed assets,
  `data/tasbir.db`, and `data/output/` are host files — no root-owned artifacts.
- Edit backend code → api reloads instantly; the worker auto-restarts; frontend
  edits hot-reload through vite.
- The playwright image is pulled from GHCR (rebuilding chromium locally is slow);
  only `api`/`worker`/`beat` build from source.

### Option B — host process (no Docker)

```bash
# Backend (API at :8000) — needs redis + a render service running
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env          # set GEMINI_API_KEY + API_KEYS
uvicorn app.main:app --reload --port 8000

# Frontend (Vite dev server at :5173, proxies /api → :8000) — another shell
cd frontend
pnpm install
pnpm run dev
```

UI at http://localhost:5173 · API at http://localhost:8000. The Vite dev
server proxies `/api/*` to the `api` service.

For a normal (non-reload) deploy: `docker compose up -d`.

## Architecture

```
n8n/Webhook → FastAPI → Celery + Redis → LangGraph Pipeline → HTML + PNG
                                                          │
                                                   Designer creates HTML
                                                   Verifier renders to PNG
                                                   via Playwright
```

### Pipeline

Strategist → Copywriter → process_all_formats. Each format tries the
**human-authored template library** first (Jinja2, `data/design_system/templates/`);
the LLM designer runs only when no template matches or the chosen one overflows.
Then Renderer injects tokens/fonts/KaTeX/images → Verifier gates (deterministic
+ overflow; templates pre-approved, LLM designs get a vision audit).

Each agent outputs typed JSON (Pydantic). Design tokens and typography live in
YAML files — the LLM never sees brand colors or hex values.

### Agent Team

1. **Strategist** (Aura Vance) — content analysis → structured brief + category + ground + template hint
2. **Copywriter** (Julian Sterling) — per-platform copy (headline, subhead, body)
3. **Template library** — human-authored Jinja2 compositions (default path)
4. **Designer** (Marcus Chen) — LLM fallback only when no template matches or it overflows
5. **Renderer** — injects tokens/fonts/KaTeX/images, saves HTML
6. **Verifier** (Victoria Thorne) — deterministic + overflow checks, vision audit for LLM designs

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

```bash
docker compose up -d             # full install / upgrade (pulls GHCR images)
```

- The Studio SPA is **built into the api image** and served at
  **http://localhost:8000** (same origin) — no separate frontend container.
- Code is baked into the images (the api image is a multi-stage build that
  bundles the SPA); config and data live in named volumes for config-driven
  control without rebuilds.
- Dependencies are pinned in `backend/pyproject.toml`; the frontend uses a
  committed `pnpm-lock.yaml`.
- The SQLite task DB and generated outputs are runtime data — gitignored,
  stored in the `tasbir_data` volume. Outputs persist until the hourly TTL
  sweep (`OUTPUT_TTL_HOURS`); downloads are repeatable, `?consume=true`
  deletes on download.
- Deployment is **local/LAN-only** (no public exposure assumed). If you ever
  expose it, put a reverse proxy with TLS in front.
- The `api`/`worker`/`beat` containers run as **root (0:0)** by default so the
  `tasbir_data` volume is always writable on first boot. If your host maps UID
  1000 and you pre-chown the volume, set `TASBIR_USER=1000:1000` in `.env`.

### Health checks

- `GET /health` — fast liveness probe (version + `llm_configured`).
- `GET /health/ready` — readiness probe that verifies **SQLite**, **Redis**,
  and the **Playwright render service**; returns `503` when any dependency is
  down. The `api` container's docker healthcheck uses this endpoint.

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/health/ready
```

### Backups (configuration)

The DB-backed configuration — design systems, templates, platforms, curated
fonts, agent configs, and runtime settings — can be exported and imported
through the API or the Studio (**Settings → Backup**). No shell scripts, no
`sqlite3`, no downtime.

```bash
# Export the whole configuration as JSON
curl -H "x-api-key: $API_KEYS" http://localhost:8000/api/system/export -o tasbir-backup.json

# Restore it on this machine (or a fresh install) — upsert/merge, never deletes
curl -H "x-api-key: $API_KEYS" -H "Content-Type: application/json" \
  -X POST http://localhost:8000/api/system/import \
  -d "$(cat tasbir-backup.json | python3 -c 'import json,sys; print(json.dumps({"payload": json.load(sys.stdin)}))')"
```

The import is **non-destructive**: existing rows are overwritten by key and
rows missing from the backup are left untouched. Tasks/audit/chats are not part
of the backup — they are per-machine runtime data.

To automate snapshots, run `curl .../export` from cron:

```cron
0 3 * * *  curl -fsS -H "x-api-key: $API_KEYS" http://localhost:8000/api/system/export \
  -o /var/backups/tasbir-$(date +\%F).json
```

### Upgrades

```bash
docker compose pull && docker compose up -d   # pull new GHCR tags + restart
```

Back up the configuration before upgrading (see above). The schema is
`create_all` + idempotent column migrations on boot — existing data survives
restarts and rebuilds.

### Monitoring & maintenance

```bash
docker compose ps                    # service status + health
docker compose logs -f api           # API logs
docker compose logs -f worker        # pipeline worker logs
# Nightly config snapshot (see Backups above):
curl -fsS -H "x-api-key: $API_KEYS" http://localhost:8000/api/system/export -o /var/backups/tasbir.json
```

Every hour, Celery beat runs `retention.sweep_expired` to remove output
artifacts and task rows older than `OUTPUT_TTL_HOURS`.

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs backend pytest + ruff and the
frontend typecheck + build on every push/PR to `main`; `.github/workflows/
publish-images.yml` builds and pushes the GHCR images.

## Development

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env   # Edit with your keys
uvicorn app.main:app --reload --port 8000
```

Frontend (another shell):

```bash
cd frontend
pnpm install
pnpm run dev               # Vite dev server on :5173, proxies /api → :8000
```

Run backend tests:

```bash
cd backend && python -m pytest
```

## Stack

- **Backend**: Python 3.12+ (FastAPI, LangGraph, Celery, Playwright)
- **Frontend**: React 19 + Vite + shadcn/ui + SWR + Monaco (Tasbir Studio)
- **Rendering**: Playwright (headless Chromium, Docker, internal-only)
- **Queue**: Celery + Redis (worker + beat for retention sweep)
- **Storage**: SQLite (tasks, config — DB-backed) + `data/output/{task_id}/` (HTML, PNG — ephemeral)
- **AI**: Gemini 3.5 Flash Lite (free tier)
- **Config**: DB-backed design systems / templates / platforms / fonts / agents / settings, seeded once from YAML
