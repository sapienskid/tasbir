# Tasbir v3 — Architecture & Design

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE (GHCR)                        │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  FastAPI  │  │  Celery  │  │  Celery  │  │ Playwright│            │
│  │  (API)   │──│  Worker  │  │   Beat   │──│  :4000   │             │
│  │  :8000   │  │          │  │ (sweeps) │  │ (render)  │            │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └──────────┘             │
│       │              │                                                │
│       │     ┌────────┴────────┐                                       │
│       │     │     Redis       │                                       │
│       │     │    :6379        │                                       │
│       │     └─────────────────┘                                       │
│       │     ┌──────────────────────────────┐                          │
│       │     │ SQLite (tasbir_data volume)  │← config + task tracking  │
│       │     └──────────────────────────────┘                          │
│       │     ┌──────────────────────────────┐                          │
│       │     │  data/output/ (volume)       │← HTML + PNG files        │
│       │     └──────────────────────────────┘                          │
│       │                                                               │
│       │  The Studio SPA is baked into the api image (served at /)     │
│       │                                                               │
│  ┌─────┴────────────────────────────────────────────────────┐        │
│  │                    External Services                      │        │
│  │  Google AI Studio  │  n8n Workflow  │  Ghost CMS          │        │
│  │  (free Gemini)     │  (triggers)    │  (content source)   │        │
│  └───────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

### Deployment model

- **Single image family, GHCR-published**: `tasbir-api` (FastAPI + Celery
  worker + beat + baked SPA) and `tasbir-playwright` (internal renderer).
  CI builds them on push (`:main`) and tags (`v*` → `:latest`).
- **No build on the server**: `docker compose up -d` pulls the images. The
  repo is only needed for development.
- **Config + data live in the `tasbir_data` named volume** — seeded on first
  boot from assets baked into the image, then Studio-owned.
- **Configuration backups are API-based** (`/api/system/export` +
  `/api/system/import`, or Studio **Settings → Backup**) — no shell scripts.

## Config Backed by the Database (Single Source of Truth)

Tasbir is **DB-backed end to end**. Design systems (brand, tokens, campaigns,
design-instruction), templates, platforms, curated fonts, agent configs, and
runtime tuning knobs are all SQLite rows the Studio owns. The YAML files under
`backend/data/design_system/` and the prompt files under `backend/config/
prompts/` only **seed** first boot (`seed-once`); from then on the DB is the
source of truth and the Studio edits rows, not files.

| Table | Owns | Seeded from |
|---|---|---|
| `design_systems` | brand identity, footer, categories, overrides, tokens, token roles, campaigns, design instruction, logo | `data/design_system/*.yaml` |
| `templates` | Jinja2 post compositions, slot features, grounds, hint tags | `data/design_system/templates/catalog.yaml` |
| `platforms` | format dimensions + family per platform | `platforms.yaml` (seed-once) |
| `fonts` | curated Google Fonts pool | `fonts.yaml` (seed-once) |
| `agents` | persona, system prompt, model, fallback models, params | `config/prompts/*.yaml` |
| `app_settings` | pipeline tuning knobs (verifier retries, concurrency, caps) | hardcoded defaults |

**Design tokens are NEVER in LLM prompts.** The designer sees variable *names*
(`var(--color-bg)`) and semantic roles; the verifier injects the actual values
after design. The `data/design_system/*.yaml` files are the seed source only.

### Why DB-backed

- **Studio-editable**: edit brand, tokens, prompts, platform dims, and knobs
  in the UI — no YAML edit, no worker restart.
- **Single source of truth**: agents, cache layers, and the Studio all read
  the same rows; no file-parse drift.
- **Portable**: the whole configuration exports/imports as one JSON document
  (`/api/system/export` / `/api/system/import`).

## Data Flow & Multi-Agent Architecture

The pipeline uses LangGraph with typed, Pydantic-validated state. Formats are
processed in parallel via `asyncio.gather` with isolated per-format branches
(no reducer races).

### Generation Pipeline Flow

```
n8n Webhook → POST /generate
          │
          ▼
   ┌──────────────┐
   │  FastAPI      │  Creates Celery task, returns {task_id}
   │  POST /generate│  n8n polls GET /tasks/{id} for status
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │  Celery Worker│  Loads the design system / templates / platforms /
   │  generate_task│  campaigns from the DB, runs the LangGraph pipeline
   └──────┬───────┘
          │
     ┌────┴────┐
     │ LangGraph│  (5 nodes)
     └────┬────┘
          │
     ┌────┴────────┐
     │Strategist   │  Aura Vance — content analysis → structured brief
     │Node 1       │  + category + ground (1 LLM call, serial)
     └────┬────────┘
          │
     ┌────┴────────┐
     │Planner      │  Aria Sol — post structure (single/carousel/story,
     │Node 2       │  ratio, slides). Hybrid: LLM only when undecided
     │             │  (platforms:["auto"], unpinned carousel); else
     │             │  deterministic PostPlan (0 LLM calls)
     └────┬────────┘
          │
     ┌────┴────────┐
     │Copywriter   │  Julian Sterling — per-platform copy in parallel
     │Node 3       │  (asyncio.gather + Semaphore). Typed JSON output.
     └────┬────────┘
          │
     ┌────┴────────────────────────────────────────────────────┐
     │ process_all_formats   — per platform, in parallel:       │
     │                                                        │
     │  Designer   Marcus Chen — HTML with var(--color-*) only │
     │  Renderer   injects tokens/fonts/KaTeX/images, saves    │
     │  Verifier   deterministic QC + overflow + vision audit  │
     │             [fail + retry<2] → back to Designer         │
     └─────────────────────────────────────────────────────────┘
          │
     ┌────┴────────┐
     │sequence_check│  carousels: same dims + i/N counter, opt-in
     └────┬────────┘  vision set-pass (sequence_audit)
          ▼
     END (success, HTML + PNG per format)
```

Template-first composition: when the plan matches a DB template, the format
branch runs `template_renderer` (deterministic Jinja2 fill) and only falls
back to the LLM designer on no-match or overflow. Save-as-template promotes
edited posts back into the library (ADR-0011).

## Agent Personas & Prompt Registry

| Agent | Persona | Node | Output |
|-------|---------|------|--------|
| Strategist | Aura Vance | `strategist` | brief, category, ground, template hint |
| Planner | Aria Sol | `planner` | post plan (platforms, ratio, slides) — hybrid |
| Copywriter | Julian Sterling | `copywriter` | per-platform copy (headline, subhead, body, tagline, badge) |
| Designer | Marcus Chen | `designer` | HTML + CSS variables (no brand values) |
| Verifier | Victoria Thorne | `quality_check` | `{pass, score, issues, critique}` |

Prompts are DB rows (`agents` table) seeded from `backend/config/prompts/*.yaml`
on first boot; the Studio **Agents** page edits them at runtime.

## Design System Configuration

### Seed files (first boot only)

```
data/design_system/
├── brand.yaml              ← Brand identity + footer + categories + overrides
├── tokens.yaml             ← CSS variable → value mappings (grayscale, 3 voices)
├── platforms.yaml          ← Platform dimensions [width, height]
├── campaigns.yaml          ← Campaign presets (tone, ground, language)
├── design-instruction.yaml ← Swiss style rules (palette, type scale, spacing)
└── templates/              ← Human-authored Jinja2 post compositions + catalog
```

### Tokens & fonts

- All design tokens live in the `design_systems.tokens` row as CSS-variable →
  value mappings. Strictly grayscale (Swiss monochrome); two grounds only
  (`white` / `black`).
- Three type voices: `--font-sans` (Inter — category/metadata/handle),
  `--font-display` (Space Grotesk — headline + wordmark),
  `--font-serif` (Source Serif 4 — subhead + body).
- The verifier injects the token values as a `<style>:root {…}</style>` block,
  auto-quoting multi-word font families (`Source Serif 4` breaks Chromium if
  unquoted), and derives the Google Fonts `<link>` from the token families +
  type-scale weights — deterministically, never LLM-decided.
- The render service waits for `document.fonts.ready` before screenshots so
  webfonts always render.

### Campaigns

Campaign presets (tone, ground `white|black`, verbal language) live per design
system in the DB. Ground priority: campaign → category (`brand.categories[].ground`)
→ white.

## Storage Architecture

### SQLite (the `tasbir_data` volume)

```
config tables:  design_systems, templates, platforms, fonts, agents, app_settings
runtime tables: generation_tasks, audit_logs, chat_threads, chat_messages, agent_jobs
```

`create_all` + idempotent column migrations on boot; existing data survives
restarts and rebuilds.

### File output (ephemeral)

```
data/output/{task_id}/
    ├── {format}.html      ← open in any browser
    └── {format}.png       ← share-ready render
```

Artifacts persist until the hourly TTL sweep (`retention.sweep_expired`,
`OUTPUT_TTL_HOURS` default 24h); downloads are repeatable, `?consume=true`
opts into delete-after-delivery (ADR-0007).

## HTML Render & Verification Pipeline

The Designer emits clean HTML + CSS with `var(--color-*)` only (no Tailwind,
no raw hex). The Renderer/Verifier injects deterministically:

1. CSS `:root` variables from the design system tokens (font families auto-quoted)
2. Google Fonts `<link>` derived from the token families + type-scale weights
3. KaTeX CDN when `<span class="math">` is detected (auto-injection)
4. Base64 `<img>` tags for embedded images + logo
5. `{{ width }}`/`{{ height }}` → parametric canvas size for templates

Then Playwright renders HTML → PNG (waits for `document.fonts.ready`), followed
by:

- **Deterministic checks** (no LLM): emoji, raw hex, footer, category, display
  face, canvas size, DOM-based overflow — hard fail + retry.
- **Multimodal audit** (Gemini Vision on the rendered PNG) → `{pass, score,
  issues, critique}`.

## System Export / Import

`GET /api/system/export` snapshots every config table (design systems,
templates, platforms, fonts, agents, app settings) into one JSON document;
`POST /api/system/import` upserts it back (merge — never deletes rows missing
from the payload) and refreshes the in-process caches so the Studio/pipeline
see the imported values immediately. Runtime data (tasks/audit/chats) is
intentionally excluded. This replaces the old shell-script SQLite backups.

## Core Design & Technical Constraints

1. **HTML + PNG Output**: Pipeline outputs `.html` + `.png`. Open HTML in any
   browser, share PNG anywhere.
2. **Strict No-Emoji Rule**: Enforced via system prompts + deterministic emoji scan.
3. **CSS Variables Only**: Designer writes `var(--color-*)` — never raw hex.
4. **Design Tokens Not in Prompts**: LLM sees variable names + semantic roles
   only; values are injected after design.
5. **DB-Backed Configuration**: design systems, templates, platforms, fonts,
   agents, and runtime settings are SQLite rows (seeded once, Studio-owned).
6. **Intra-Node Format Concurrency**: `asyncio.gather()` with isolated
   per-format branches (no reducer races).
7. **Typed Agent I/O**: Every agent uses Pydantic models, not markdown parsing.
8. **Brand Context Everywhere**: Brand name/tagline/mission flows to all agents.
9. **Automatic KaTeX Injection**: Math spans auto-detect and inject the CDN.
10. **Deterministic Font Loading**: Families auto-quoted; `document.fonts.ready`
    awaited before screenshots.
11. **Overflow Is a Hard Failure**: DOM-based overflow detection fails + retries
    clipped text.
12. **Fail-Closed Auth**: `x-api-key` on all `/api/*` routes + per-key Redis
    token-bucket rate limiting.
13. **Render Service Is Internal**: Playwright is not published to the host;
    requires `RENDER_SERVICE_KEY`.
14. **SSRF-Guarded Image Fetch**: every image URL validated (block
    loopback/link-local/metadata, allow LAN, size/redirect caps).
15. **Sanitized LLM/Edited HTML**: Designer output and rerender payloads pass
    through the HTML sanitizer before rendering/saving.
16. **Ephemeral Artifacts**: files persist until the hourly TTL sweep; downloads
    repeatable, `?consume=true` opts into delete-after-delivery (ADR-0007).
17. **Manual Edit → Re-render**: `POST /tasks/{id}/formats/{fmt}/rerender`
    renders edited HTML without the designer LLM; vision audit opt-in (ADR-0010).
18. **Template-First Composition**: DB templates tried before the LLM designer;
    `data-slot` promote loop (ADR-0011).
19. **Typed Media Tools**: LLM-decided `find_photo`/`illustrate` (DiceBear,
    25 curated styles) — never forced, SSRF-guarded, cached once per post.

## Docker & Deployment

- `backend/Dockerfile` — multi-stage api/worker/beat image: builds the SPA in
  stage 1 (Node), installs pinned Python deps in stage 2, copies the SPA to
  `/app/static`. Context = repo root.
- `backend/Dockerfile.playwright` — slim render service (`--only-shell`
  chromium headless shell), internal network, `RENDER_SERVICE_KEY`-authed.
- `docker-compose.yml` — GHCR pulls (`tasbir-api`, `tasbir-playwright` +
  `redis:7-alpine`), healthchecks on all services, `restart: unless-stopped`,
  `beat` runs the hourly retention sweep, no host port for Playwright.
- Named volume `tasbir_data` holds the SQLite DB + seed assets + generated
  outputs; first boot seeds config, thereafter Studio-owned.
- Configuration backups are API-based (`/api/system/export` / `/import`) —
  no shell scripts, no `sqlite3`.
