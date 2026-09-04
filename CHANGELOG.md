# Changelog

All notable changes to Tasbir are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-09-04

### Fixed
- **Markdown sanitization in copywriter** — `_clean_markdown()` strips raw markdown syntax (`**`, `*`, `##`, `-`, `` ` ``, `---`, `![[...]]`, `![...]`) across all copywriter paths (LLM output, fallbacks, verbatim, and repairs) into clean editorial text.
- **Carousel slide retry & validation** — `validate_platforms()` now parses and accepts individual carousel slide IDs (e.g. `instagram-carousel-portrait-5`); `build_retry_state()` populates `slide_context` and cleans stored copy.
- **Copywriter token scaling** — Raised default `max_tokens` from 2,000 to 4,000 and dynamically scale for multi-slide carousels (`slides * 450 + 1000`).
- **Markdown web image auto-discovery** — `![alt](https://...)` URLs in source content are automatically extracted and passed to the media pipeline.

### Changed
- **Memory & Resource Optimization (< 1 GB RAM)** — Capped total compose memory footprint across all 5 containers to 944 MB:
  - `playwright`: 384 MB limit with low-memory Chromium launch flags (`--disable-gpu`, `--disable-software-rasterizer`, `--renderer-process-limit=1`, `--disable-extensions`, `--disable-background-networking`, `--mute-audio`).
  - `api`: 192 MB limit (`uvicorn --workers 1`).
  - `worker`: 256 MB limit (`celery --concurrency=1`).
  - `redis`: 48 MB limit (`--maxmemory 32mb`).
  - `beat`: 64 MB limit.

## [1.0.0] — 2026-08-03
- **Per-slide media plan** — one LLM planning session per post decides each
  slide's media (photo / illustration / none) via a structured plan
  (`app/services/media_plan.py`), executed in parallel per slide. Slides
  filled by a user image are skipped. Fixes the "same image on every slide"
  defect (see ADR-0018).
- **Unified Scene Composer** — `app/services/tools/composer.py` assembles a
  deterministic editorial figure from custom category heroes
  (`illustrations/heroes/`), Lucide motifs, Highlights CC0 hand-drawn marks,
  DiceBear figures, and procedural geometry under **22 named composition
  archetypes**. All colors resolve through `--ill-*` → `--color-*` tokens, so
  figures follow the active design system.
- **Vendored Lucide icon library** — 1,756 ISC line icons in
  `data/icons/lucide/` with a generated `icons.yaml` catalog; `icon_search`
  tool for deterministic content-mapped motif discovery.
- **Vendored Highlights kit** — 117 CC0 hand-drawn SVG marks in
  `illustrations/highlights/` (arrows, underlines, sprinkles, loops, ...).
- **`content_summary` on the Strategist brief** — key themes + searchable
  keywords that feed the media plan's queries and motif choices.
- **`illustration_style`** — optional `POST /generate` field and a DB-backed
  design-system default; precedence: API → media plan → DS default → `compose`.
- **Big numeral = slide number** — `index-numeral`, `portrait-index`, and
  `story-costs` templates show the real slide index on carousels.
- **User-image auto-distribution** — carousel images are assigned image i →
  slide i (wrapping), embedded per slide.
- **Duplicate-media QC guard** — the sequence check fingerprints embedded
  media per slide; identical media on 2+ slides is a hard issue with a bounded
  retry.

### Changed
- **DiceBear pruned to a 9-style keep-list** — `open-peeps`, `lorelei`,
  `notionists`, `bottts`, `blobs`, `initials`, `shapes`, `waves`, `landscape`.
  The `illustrate` tool's `style` enum is now `compose` | `procedural` |
  DiceBear id; the old `anthropic` alias maps to `procedural`.
- **Media model** — per-post photo/illustration caching replaced by the
  per-slide media plan; the designer/template media directors consume plan
  entries.
- **System export/import API** — `GET /api/system/export` snapshots the whole
  configuration (design systems, templates, platforms, fonts, agents, runtime
  settings) as one JSON document; `POST /api/system/import` upserts it back
  (merge — never deletes rows missing from the payload) and refreshes the
  in-process caches. Available in the Studio at **Settings → Backup**. Replaces
  the old `scripts/backup-db.sh` / `scripts/restore-db.sh` SQLite snapshot flow.

### Changed
- **Shell scripts removed** — `scripts/install.sh`, `scripts/backup-db.sh`,
  `scripts/restore-db.sh` are gone; configuration backup/restore is now
  API-based (`/api/system/export` + `/api/system/import`).
- **Local-only compose variants removed** — `docker-compose.dev.yml` and
  `docker-compose.network.yml` dropped; the production `docker-compose.yml`
  (GHCR pulls) is the only compose file. `frontend/Dockerfile` (dev-only build
  stage) removed — the SPA is built inside the api image.
- **Single-image deploy** — the Studio SPA is built into the `tasbir-api`
  image (multi-stage `backend/Dockerfile`) and served at `/`; the separate
  `frontend` service, `frontend-dist` volume, and `tasbir-frontend` GHCR image
  are removed. Compose files and CI updated accordingly.
- **DiceBear part-based illustrations** — the `illustrate` tool's `open-peeps`/
  `open-doodles` styles (which selected from ~120 vendored whole-figure CC0
  SVGs) are replaced by a curated allowlist of **25 DiceBear styles** rendered
  via the official Python bindings (`dicebear-core`/`dicebear-styles`,
  offline + deterministic). Output uses the `line` palette (bold 2-tone
  ink/paper, recolored to `var(--color-*)`). People/robot styles support
  **part pinning** (`facial_hair`, `hair`, `expression`, `accessory` — e.g.
  `moustache3`). Vendored `backend/data/illustrations/` and
  `backend/scripts/fetch_illustration_kits.py` removed. CC BY 4.0, text,
  emoji, micro-canvas and gradient-based styles are excluded (see ADR-0016).
- **Dependencies updated to latest** — backend pinned to newest verified
  versions in `pyproject.toml` (fastapi, uvicorn, langgraph/langchain stack,
  google-genai, openai, pydantic, etc.); frontend bumped (react 19, vite 8,
  typescript 7, react-router 7.18) with a regenerated `pnpm-lock.yaml`.
  `backend/requirements.txt` removed — `pyproject.toml` is the single source
  of truth.
- **Repo cleanup** — removed stale design doc, dead `requirements.txt`, empty
  dirs, stray `subagent-*` worktrees, and local caches.
- **Single `v1.0.0` release tag** — intermediate `v1.0.1`/`v1.0.2` tags and
  GHCR image versions removed; images re-published multi-arch (amd64+arm64)
  as `:1.0.0` + `:latest`.

## [1.0.0] — 2026-08-03

First production release. Focused on a stable, self-hosted deployment with a
clean CI pipeline, explicit ops tooling (backups + health checks), and the
task-based template/design-system creation flow.

### Added

- **Task-based agent jobs** — template creation and the brand builder now run
  as background jobs tracked on the Tasks page. Closing the dialog or leaving
  the page never loses a job.
  - `GET /agent-jobs` (Tasks-page integration), `DELETE /agent-jobs/{id}`
  - `/jobs/:id` detail page with status + created-template/design-system links
- **One-shot template build** — `POST /templates/from-input` accepts an
  **image**, **HTML**, or a **text description** (+ ratio + ground) as context,
  then authors → validates → saves a template directly. Old-style dialog with
  inline job status; no chat.
- **Template counts row** on the Templates page (total / active / inactive +
  per-family), and `?open={template_id}` deep-links into the edit dialog.
- **`repair_jinja`** — recovers LLM-fused Jinja block-closes (e.g.
  `{% endif %>`) so authored drafts parse and render instead of failing with
  `expected token 'end of statement block'`.
- **`/health/ready`** — readiness probe (SQLite + Redis + Playwright render
  service); the docker healthchecks now use it.
- **`scripts/backup-db.sh` / `scripts/restore-db.sh`** — WAL-safe SQLite
  snapshots and restore.
- **`scripts/install.sh`** — one-command install / upgrade for self-hosters.
- **GitHub Actions CI** (`.github/workflows/ci.yml`) — backend pytest + ruff,
  frontend typecheck + build, on push and PR.
- `CHANGELOG.md`, `.env.example` refresh (`RENDERER_URL`), README ops section.

### Changed

- Template creation reverted from a chat-inbox prototype to the old-style form
  flow (per user feedback) while keeping task-based background execution.
- Bumped backend (`0.5.0`) and frontend (`0.1.0`) to **1.0.0**.
- Ruff lint baseline cleaned to zero violations.

### Security

- API auth fails closed (`API_KEYS`), per-key Redis rate limit, SSRF-guarded
  image loading, HTML sanitizer, input caps, internal-only key-authed Playwright
  service. (Pre-existing; reaffirmed for the release.)

## [0.5.0] — earlier

DB-backed design systems, template library, brand builder, and the agent-chat
editing loop.

### Added

- DB-backed design systems (brand, footer, categories, campaigns, tokens,
  design-instruction, logo) — Studio-editable, seed-once from YAML.
- DB-backed platform dimensions, curated Google Fonts pool, and runtime tuning
  knobs (Studio Settings).
- DB-backed template library (16 seeded + AI-generated), template-first pipeline
  with LLM fallback, anti-repeat via Redis, promote-edited-post learning loop.
- Brand Builder agent (form + reference/logo images → design system + starter
  templates).
- Template Author agent (mockup image → validated Jinja2 template).
- Agent chat (`GET/POST /tasks/{id}/chat`) — vision-capable design assistant
  proposing replacement HTML with review-then-render.
- Visual editing (locked-down GrapesJS canvas), bulk ZIP download,
  save-as-template.

## [0.4.0] — earlier

Initial v3 pipeline.

### Added

- Five-agent LangGraph pipeline (Strategist → Planner → Copywriter →
  process_all_formats → Verifier) with typed Pydantic I/O.
- YAML design system (`brand`, `tokens`, `platforms`, `campaigns`,
  `design-instruction`), strict monochrome Swiss typography.
- Playwright render service (internal-only, key-authed), deterministic QC +
  DOM overflow detection + Gemini Vision audit.
- KaTeX/Mermaid injection, SSRF-guarded image embedding, ephemeral artifact
  delivery with TTL sweep, manual edit → re-render.
- SQLite task tracking, Celery + Redis, hourly retention sweep.

---

The v1/v2 lineage (Cloudflare Workers prototype, Penpot-native design) is
historical and not part of this changelog's scope.
