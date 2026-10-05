# Changelog

All notable changes to Tasbir are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Per-format ground and design language on AI-generated posts** — an AI post
  could never change its own ground or design language, because those values were
  stored only at *task* level (`strategic_brief.ground`, `source_data.style_language`)
  and baked in at generation time. They are now part of the format's recipe and
  editable per format, so the Studio's structured editor has the same controls
  Manual Compose has (`components/tasks/recipe-controls.tsx`). Each is a recipe
  override that forces a full template re-fill.
- **`category` is a per-format recipe override** too, closing the last of the
  three task-level values that blocked parity with the composer.
- **"Convert to a template" for designer posts** (`components/tasks/convert-panel.tsx`)
  — the backend could always convert a designer-LLM post, but the Studio had no
  control for it: the only trigger was switching design system, and that dropdown
  only renders with 2+ design systems. With a single system there was no way to
  convert at all, so those posts were uneditable except through raw HTML. The
  dialog picks a template, warns that the freeform layout is replaced, and notes
  that the original is kept as `{fmt}.designer.html`.
- **`GET …/editor` reports `render_stale`** and the editor shows a "Render PNG"
  action with a "PNG is behind the saved design" hint, so the save/render split
  is visible rather than silent.

### Changed
- **Saving a post no longer renders it.** `POST …/refill` takes `render`
  (default `true`, so existing clients are unaffected); autosave sends
  `render: false`, which persists the recipe + HTML and skips the headless
  render and the hard checks. Measured on a live carousel post: **3.3s → 37ms**,
  and the response drops from ~134 KB to ~11 KB (128 KB of the old payload was
  the base64 PNG). This is the fix for "the AI editor feels slow" — saves are
  serialized per task, so a 3.3s save was blocking every subsequent edit of every
  other format of that task. Rendering is now an explicit action; until it runs,
  the PNG lags the HTML and `render_stale` says so.

### Fixed
- **A ground/template mismatch is now rejected instead of silently mis-rendered.**
  Refill never consulted the template's `grounds` list, so a black-ground post
  could be refilled onto a `grounds: ["white"]` template: the template's
  `{% if ground == "black" %}` branch still fired and produced black CSS on a
  white-only layout, with no 422 and no warning. The picker badge that hinted at
  the restriction was cosmetic.

### Changed (internal)
- **`FormatRecipe` is the single record of a format** (`app/services/format_recipe.py`).
  `template_id` / `copy` / `editor` were per-format while `ground`,
  `style_language` and `category` were task-level, so re-rendering had to
  re-derive values that belonged to the format. `read_recipe()` synthesizes a
  recipe for rows written before recipes existed, reproducing the previous
  derivation exactly — no migration, existing posts render identically — and a
  corrupt stored recipe falls back to synthesis rather than bricking the post.
  Legacy keys are still written in sync, so EditorState, the result shape,
  media_credits and retries are unaffected.
- The recipe flattens copy into `headline`/`subhead`/`body`/`tagline`/`extra`
  rather than nesting it, since those are already the slot names the editor and
  templates speak.

### Changed (earlier in this release)
- **Settings is now nested routes with a left nav** — `/settings` redirects to
  `/settings/platforms`, and each section (`platforms`, `fonts`, `runtime`,
  `system`) is its own route and its own lazily-loaded chunk. Previously the page
  was one file of tab panels that unmounted and refetched on every switch and
  had no deep links. `AppShell` needed no change — its `/settings` match already
  covered sub-routes.
- **Runtime knobs are typed and validated on the server** — every setting in
  `DEFAULT_APP_SETTINGS` now carries `type` (`int` / `float` / `bool`) plus
  `min` / `max` / `step`, and `PUT /api/settings` validates the batch before
  writing anything. A bad value returns **422** naming the key and leaves the
  database untouched. Previously arbitrary JSON (`verifier.max_retries: "abc"`)
  persisted and was handed straight to consumers. Stored values that predate the
  contract are self-healed back to their default on read rather than crashing a
  consumer.
- **The Studio renders knob controls from the server's type contract** —
  `RuntimeKnob` picks a checkbox or a bounded number input from `spec.type`, so
  the three boolean knobs (`verifier.clef_first`, `claims.hold_on_mismatch`,
  `publish.enabled`) are real checkboxes again instead of number inputs
  coercing `true` to `1`. Per-row dirty dots with revert, a save button that
  counts pending changes, and a confirmation behind "Reset to defaults".
- **Config routes use the interactive rate-limit bucket** — `platforms`,
  `fonts/pool`, `fonts/search`, `settings`, `models`, `agents`,
  `design-languages` and `system` declare `interactive_rate_limiter` (600/min)
  instead of sharing the 30/min generation bucket, so browsing the Studio no
  longer competes with `POST /generate`. The parent `rate_limiter` dependency
  was removed from those `include_router` calls, otherwise both buckets were
  consumed per request.
- **Single source of truth for platform families and font roles** —
  `services.platforms.VALID_FAMILIES` and `services.fonts.VALID_ROLES` are
  imported by the API layer (which redeclared them) and published to the Studio
  via the new `GET /api/settings/meta`, so the frontend derives its dropdowns
  instead of hardcoding `FAMILIES` / `FONT_ROLES`.
- **The Agents page no longer shows model names** — the graph nodes, the aux
  agent cards and the config rail previously rendered the model id; the rail now
  says model routing is code-owned via the AI Gateway and drops the read-only
  field. Model routing is unchanged (it was already ignored on write).
- **`/health` reports the real version** from package metadata / `pyproject.toml`
  instead of a hardcoded `1.0.1` that had drifted to `1.2.0`.
- **Design languages expose their full row** — `GET /api/design-languages`
  returns `base`, `source`, `is_active` and `sort_order` alongside the palette,
  and `GET /api/design-systems/styles` returns `source` / `is_active` so the
  Studio marks immutable built-ins from real provenance instead of matching
  label/name strings.

### Added
- **`GET /api/settings/meta`** — the platform-family and font-role vocabularies.
- **`GET /api/system/info`** — a read-only view of the environment actually in
  force (version, Gateway/Redis/render/photo-key presence as booleans, rate
  limits, retention, `SKIP_VERIFY`/`COPY_QA_ENFORCE`, and row counts), surfaced
  in a new **System** settings section. Secret-shaped settings are never echoed.
- **Search, show-inactive and delete confirmation** for Platforms and Fonts —
  both tables deleted on click with no confirmation, which was easy to do by
  accident and (for a platform) silently changed every render size in that
  family.
- **Import previews the backup before applying** — the System section parses the
  file, shows per-table row counts, and requires an explicit confirmation before
  touching the database.

### Fixed
- **The render-service client failed open *slowly*** — `RENDER_TIMEOUT` (45s) was
  applied as the **connect** timeout, so every PNG render and DOM overflow check
  against an unreachable Playwright service stalled the full 45s before giving
  up. Connect and render budgets are now split (`httpx.Timeout(45s,
  connect=3s)`): rendering still gets its generous budget, but a service that is
  down or unreachable now fails open in milliseconds. This is what made the
  template test suite appear to hang (250s+ for 16 tests); it now runs in ~24s,
  and the whole backend suite went from 4m11s to ~2m.
- **`design_languages` was missing from the config backup** — `GET
  /api/system/export` / `POST /api/system/import` silently dropped every
  **custom** design language, so a restore lost them. They are now exported and
  restored losslessly (including each language's `di` rules bundle). Code-owned
  built-in presets (`source: "seed"`) are skipped on import because they always
  resolve live from `styles.STYLE_PRESETS` — restoring a stale copy would only
  corrupt their bookkeeping columns.
- **Backup schema is now version 2** (`SCHEMA_VERSION` 1 → 2) since a new table
  was added. **Version 1 payloads still import** — a table the payload's version
  predates is simply absent, and because import never deletes, local rows
  survive.
- **Template preview and validation use the platforms table** — the canvas was a
  hardcoded `DIMS` dict in `api/templates.py`, so resizing a platform in
  Settings had no effect on previews and the two silently drifted. They now come
  from `platforms.family_dims()` (first active platform per family, falling back
  to the seed dims).
- **One base64 upload cap** — `/api/compose` allowed 10 MB and
  `/api/tasks/{id}/formats/{fmt}/refill` allowed 15 MB for the same payload.
  Both now use `app/core/limits.MAX_UPLOAD_B64` = 10 MB, matching the default
  `IMAGE_MAX_BYTES`.
- **Font weights report invalid input** — a bad comma-separated weight was
  silently dropped from the list instead of surfacing an error.
- **`reset_runtime_settings` silently reset nothing** when a knob row was
  missing, because the repository `update` is a no-op on an absent row. It now
  creates the row.
- **Preview platforms refresh the dimension caches** — saving a platform now
  re-warms the module-level `FORMAT_DIMS` / `FAMILY_DIMS` maps that every render
  and preview size is read from.

### Migration notes
- **Base64 image uploads are now capped at 10 MB on the task-refill endpoint**
  (was 15 MB). Clients sending larger images get a 422. To keep the old limit,
  raise `app/core/limits.MAX_UPLOAD_B64`.
- Config backups taken before this release (`schema_version: 1`) remain
  importable; re-export to capture custom design languages.
- Old `/settings?tab=…` style links do not exist (tabs were never in the URL),
  but bookmarked `/settings` still works and redirects to `/settings/platforms`.
- Tests now point `renderer_url` at a closed local port (`tests/conftest.py`),
  matching what they already did for Redis. Overflow checks and renders fail
  open there, so behaviour is unchanged — only the wait is gone.

## [1.2.0] — 2026-10-04

**Breaking (deployment):** every LLM call now goes through the Cloudflare AI
Gateway. `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_AI_GATEWAY_TOKEN` are required
(`GEMINI_API_KEY` is no longer read at runtime); `LLM_PROVIDER` and
`OPENROUTER_API_KEY` are gone. Route specs + policy: `docs/ai-gateway-routes.md`.

**Operators:** pin `TASBIR_IMAGE_TAG` (do not run `:latest`) — see the release
procedure in AGENTS.md.

### Changed
- **Gateway-only LLM transport (direct Google deleted)** — `services/llm.py` and `services/vision.py` talk exclusively to the Gateway compat endpoint (OpenAI chat shape): plain chat, function-calling, the multi-turn media tool loop, and vision audits all go route-first (`dynamic/tasbir-{fast,creative,vision}`) → `google-ai-studio/{model}`. Tools and `image_url` vision verified live through both a route and a direct-model compat call. Deleted: the direct `ChatGoogleGenerativeAI` chain, the OpenRouter fallback, `LLM_PROVIDER`/`OPENROUTER_API_KEY`, and the `langchain-*`/`openai` dependencies. A total Gateway failure now raises (fail-loud) instead of silently bypassing quotas, logging, and caching. `/health` reports Gateway credentials; unknown env vars are ignored.
- **Fixed the Google provider slug** — the `google/{model}` slug returns `400 Model not found` in this account; `google-ai-studio/{model}` is the only working slug on both the compat host and the unified API path.
- **Decision judgments drive quality (Clef)** — `image-relevance` is wired (photo-vs-headline judged on the render; a confident mismatch/clash forces a designer retry); `media-kind` pre-gates the media director (abstract subjects skip photo search); Clef vision runs *before* the Gemini audit and a clean pass skips it; hard flags cap the score at 60 so they force real retries; copy figures are deterministically grounded against the source (invented numbers force a rewrite and hold publish); a per-format publish/hold gate is recorded in the task result. New runtime knobs: `verifier.clef_first`, `claims.hold_on_mismatch`, `publish.enabled`. Calibration sampling defaults to 5%.
- **Agent model controls removed from the Studio** — routing is code-owned (`MODEL_ROUTES` + Gateway routes). The Agents page shows the effective model read-only and `PUT /api/agents/{name}` ignores `model`/`fallback_models` (a Gemma pick used to silently break JSON-only agents whenever the route was healthy).
- **Long articles no longer blow the token budget** — content over 12K chars is judged by Clef-flash then compressed by Gemini 3.1 Flash Lite into a brief (~92% smaller) that downstream agents read; Gemma (16K TPM) only ever sees the brief. A free-tier quota tracker reserves tokens before each call so parallel formats cannot 429 mid-pipeline.
- **Jev decision model removed** — Clef / Clef-flash only.

### Added
- **Cloudflare AI Gateway transport + Clef decisions** — decision client (`services/decisions.py`) runs Clef-flash (fast text) + Clef (vision/precision) on Workers AI (Neuron-billed, no Gateway credits needed) with failover and calibration dual-run logging; versioned question packs (`services/decision_packs.py`) with composite copy-quality scoring. Wired fail-open/advisory: strategist intake safety gate + taxonomy second vote, per-platform copy QA with a bounded rewrite loop, designer semantic check, verifier pregate, media-plan vote, and a `refine-focus` loop driver that picks the single highest-leverage fix or stops the retry loop early. New env: `CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_AI_GATEWAY_TOKEN, CF_GATEWAY_ID, DECISION_PROVIDER_ORDER, DECISION_CALIBRATION_RATE, COPY_QA_ENFORCE`.
- **Human feedback endpoint** — `POST /api/tasks/{id}/feedback` records approve/reject verdicts (audit rows) for decision-threshold tuning.
- **Bundled brand design systems (ADR-0022)** — Fundaments.work and Theorem seed on first boot, each with its own brand design language (custom `design_languages` row), palette, fonts, rules, per-ground logo variants, and its own copy of the standard layouts. Seed-owned rows refresh on restart, Studio edits are never overwritten.
- **Templates honour the design language** — accent devices inside `{% if has_accent %}`, radius/shadow/headline-weight via tokens, a brand-logo slot with clear space, and a visible subhead on both grounds (previously invisible on black in 7 templates, missing from 5). An LLM-designed post in an accent language must use the accent (verifier gate).
- **New design systems start with no language** and get their own user-owned copy of the standard layouts.

### Fixed
- **Dev stack stability** — uvicorn `--reload` no longer restarts on `data/` writes (renders no longer interrupt in-flight API requests), and the Celery beat container no longer OOMs (memory limit 64m → 256m).
- **Deadlock in the quota tracker** — `seconds_until_fit()` held a non-reentrant lock while re-entering `usage()` (fixed with `RLock`).

### Removed
- **Direct Google AI calls, LangChain, and the OpenRouter fallback** — no code path reaches `googleapis.com` directly any more.

## [1.1.0] — 2026-09-28

### Added
- **Manual Compose (zero AI)** — `/api/compose` builds posts from an operator-chosen template, copy, and media; a batch of up to 20 posts (carousels 2–10 slides) becomes one task per post, rendered by the no-LLM `compose_task`, re-openable via `PUT /api/tasks/{id}/composition`. Shared `ds_context.resolve_ds_context` + `composer.finalize_html` replace the duplicated design-language and token/font/KaTeX/image/logo injection code (see ADR-0021).
- **Agent structured editing** — `POST /api/tasks/{id}/formats/{fmt}/refill` applies slot text, element toggles, media position, media (upload / stock photo / illustration), or a template switch to template-built posts (slot replacement via BeautifulSoup, full template re-fill preserving or replacing media) and re-renders through the deterministic hard gate. The Studio editor is compose-style: Content panel (Template/Text/Media tabs reusing the composer fields, caps, and media picker) with debounced auto-save of touched fields only (converges with inline edits instead of clobbering them), always-live click-to-edit WYSIWYG preview, agent chat open by default.
- **Instant structured editing (ADR-0023)** — `POST /api/tasks/{id}/formats/{fmt}/refill/preview` returns the finalized document with no PNG, checks, or writes (shared `_build_refill`, ~10-20 ms; heavy base64 payloads are hoisted out of the structural passes), and `GET …/editor` restores toggles / media position / media kind after a reload. `refill` is now serialized per (task, format) with the latest HTML re-read under the lock (concurrent edits merge), writes files atomically, survives a PNG-service outage (HTML still saved), and returns `html`, `revision`, `saved_at`, `editor`, `converted`. Designer-LLM posts convert to a template post via `template_id` (original kept as `{fmt}.designer.html`). A separate interactive rate-limit bucket (`RATE_LIMIT_INTERACTIVE_PER_MIN`, default 600) covers compose previews/thumbnails and the editor endpoints.

### Removed
- **GrapesJS visual editor** — the parallel canvas was never WYSIWYG (own wrapper divs, re-parsed CSS, divergent font/token resolution); direct slot editing in the real preview document replaces it, and the `grapesjs` dependency is dropped.

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
