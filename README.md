# Tasbir v1.0.0

AI-powered social media asset pipeline. Blog content goes in,
platform-optimized HTML + PNG renders come out. Zero API costs.
Self-hosted via Docker.

> **For AI agents**: Read [AGENTS.md](AGENTS.md) before making changes.
> **For project plan**: See [PLAN.md](PLAN.md).
> **For architecture**: See [DESIGN.md](DESIGN.md).
> **For design decisions**: See [docs/adr/](docs/adr/) and [docs/glossary.md](docs/glossary.md).
> **For releases**: See [CHANGELOG.md](CHANGELOG.md).

## Quick Start (Install)

One command installs the whole system (prerequisites + `.env` with generated
API keys + image build + stack start):

```bash
# From a checkout:
bash scripts/install.sh

# Or clone-and-install in one line:
bash -c "$(curl -fsSL https://raw.githubusercontent.com/sapienskid/tasbir/main/scripts/install.sh)"
```

The installer:
- Checks for Docker + the compose plugin
- Clones the repo (one-liner path) or uses your checkout
- Creates `.env` from `.env.example`, **generating strong `API_KEYS` and
  `RENDER_SERVICE_KEY`** and prompting for `GEMINI_API_KEY`
- Runs `docker compose build` + `docker compose up -d`
- Waits for `/health` and prints your API key + next steps

Open http://localhost:8000 — the Tasbir Studio SPA is served by the API itself.
API docs at http://localhost:8000/docs. Auth fails closed: every `/api/*`
request needs `x-api-key` (set it in the Studio header dialog).

> **LAN/self-hosted only.** Do not expose port 8000 to the public internet
> without a TLS reverse proxy in front.

## Manual Install (optional)

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY + API_KEYS (and RENDER_SERVICE_KEY for Docker)
docker compose up -d --build
```

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
bash scripts/install.sh          # full install / upgrade
```

- The Studio SPA is built into the `frontend` image and staged into a shared
  volume the API serves at **http://localhost:8000** (same origin).
- Code is baked into the images (`--build` after code changes); config
  (`config/prompts/`) and data (`data/design_system/`, `data/output/`) are
  bind-mounted for config-driven control without rebuilds.
- Dependencies are pinned in `backend/pyproject.toml` and
  `backend/requirements.txt`; the frontend uses a committed `package-lock.json`.
- The SQLite task DB (`backend/data/tasbir.db`) and generated outputs are
  runtime data — gitignored. Outputs persist until the hourly TTL sweep
  (`OUTPUT_TTL_HOURS`); downloads are repeatable, `?consume=true` deletes on
  download.
- Deployment is **local/LAN-only** (no public exposure assumed). If you ever
  expose it, put a reverse proxy with TLS in front.

### Health checks

- `GET /health` — fast liveness probe (version + `llm_configured`).
- `GET /health/ready` — readiness probe that verifies **SQLite**, **Redis**,
  and the **Playwright render service**; returns `503` when any dependency is
  down. The `api` container's docker healthcheck uses this endpoint.

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/health/ready
```

### Backups (database)

The runtime database is a single SQLite file (`backend/data/tasbir.db`), the
source of truth for design systems, templates, and tasks. Back it up regularly.

```bash
# Snapshot while the stack is running (WAL-safe online backup, no downtime)
scripts/backup-db.sh                 # → backend/data/backups/tasbir-<timestamp>.db
scripts/backup-db.sh -o /mnt/backup  # custom output dir
scripts/backup-db.sh -k 14           # keep only the newest 14 snapshots
```

Add a cron job (as the user owning the repo):

```cron
0 3 * * *  cd /path/to/tasbir && scripts/backup-db.sh -k 14 >> /var/log/tasbir-backup.log 2>&1
```

**Restore** (requires `sqlite3`):

```bash
# 1. Stop the stack so nothing writes mid-restore:
docker compose stop api worker beat
# 2. Restore (auto-backs-up the current DB first):
scripts/restore-db.sh backend/data/backups/tasbir-20260803-030000.db
# 3. Start again:
docker compose start api worker beat
```

### Upgrades

```bash
bash scripts/install.sh          # git pull + rebuild + restart (idempotent)
```

or manually:

```bash
git pull
docker compose build && docker compose up -d
```

Back up the DB before upgrading. The schema is `create_all` + idempotent
column migrations on boot — existing data survives restarts and rebuilds.

### Monitoring & maintenance

```bash
docker compose ps                    # service status + health
docker compose logs -f api           # API logs
docker compose logs -f worker        # pipeline worker logs
scripts/backup-db.sh -k 14           # nightly DB snapshot
```

Every hour, Celery beat runs `retention.sweep_expired` to remove output
artifacts and task rows older than `OUTPUT_TTL_HOURS`.

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs backend pytest + ruff and the
frontend typecheck + build on every push/PR to `main`.

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
