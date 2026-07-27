# Tasbir v2 — Project Plan

A fully agentic, Python-based social media asset pipeline. Zero API costs.
Self-hosted via Docker, no SaaS dependencies.

## Mission

Convert blog content into platform-optimized social media images using a
multi-agent AI pipeline — completely free to run, with Penpot for design
token management and human-in-the-loop refinement.

## Core Principles

1. **Zero API costs** — Gemini free tier, CSS gradients, Unsplash free tier
2. **Self-hosted** — Everything in Docker, no SaaS dependencies
3. **Design token driven** — Penpot & DTCG standard as source of truth for visual tokens
4. **Parallel Agentic Studio** — LangGraph state machine with fan-out parallel agent execution
5. **Async by default** — Celery tasks, SSE streaming, webhook triggers

## Phase Progress

### Phase 1: Foundation — Docker + Basic API (Completed)
- [x] `docker-compose.yml` with all core services
- [x] FastAPI app skeleton with health check
- [x] PostgreSQL schema + Alembic migrations
- [x] Redis + Celery configuration
- [x] MinIO for object storage
- [x] Caddy reverse proxy configuration

### Phase 2: Data Layer — Models + API Routes (Completed)
- [x] SQLAlchemy models (settings, templates, tasks, assets, prompts, formats, tokens)
- [x] CRUD API for settings
- [x] CRUD API for templates
- [x] CRUD API for design tokens
- [x] CRUD API for output formats
- [x] CRUD API for prompts (prompt registry + version history)
- [x] Task tracking (status, results, error handling)

### Phase 3: AI Layer — LLM Service + Backgrounds (Completed)
- [x] Google Gemini client (free tier via AI Studio)
- [x] LiteLLM integration (fallback provider support)
- [x] Background service: CSS gradients + SVG patterns (zero cost)
- [x] Background service: Unsplash API (free stock photos)
- [x] Background service: Solid colors + geometric patterns

### Phase 4: Agent Engine — LangGraph Parallel Pipeline (Completed)
- [x] `prompt_registry` table — all prompts stored in DB with versioning
- [x] **Strategist agent (Aura Vance)**: content analysis, campaign brief
- [x] **Copywriter agent (Julian Sterling)**: visually structured copy, strict no-emoji rule
- [x] **Visual Director agent (Elena Rostova)**: art direction, CSS backgrounds & Unsplash tools
- [x] **Designer agent (Marcus Chen)**: standalone HTML graphic canvas with Tailwind + Google Fonts
- [x] **Quality agent (Victoria Thorne)**: output validation, refinement loop
- [x] **Token Generator agent (Dr. Soren Lindqvist)**: DTCG design token architecture
- [x] **Parallel Execution**: LangGraph fan-out (`strategist` -> `[copywriter, visual_director]` -> `designer`)
- [x] **Intra-Node Format Concurrency**: `asyncio.gather()` parallel format processing
- [x] **Dynamic DB Formats**: `app.services.formats.get_format_info()` dynamic injection
- [x] **Post-Processing Cleanup**: `cleanup.py` emoji stripping & button artifact conversion

### Phase 5: Rendering + Storage (Completed)
- [x] Playwright HTTP service (HTML → PNG screenshot rendering)
- [x] MinIO asset storage and retrieval
- [x] Asset URL generation with task scoping

### Phase 6: Ghost + Penpot Integration (Completed / In Progress)
- [x] Ghost webhook handler (`post.published` → auto-generate)
- [x] Ghost Admin API client (JWT auth, content fetching)
- [x] DTCG token format conversion (internal ↔ W3C standard)
- [ ] Penpot MCP client bidirectional sync refinements

### Phase 7: Frontend — SvelteKit + shadcn-svelte (Completed)
- [x] SvelteKit project with TypeScript
- [x] Dashboard page — pipeline hero, stat cards, recent tasks
- [x] Create page — two-column form, format grid, SSE streaming
- [x] Configure page — tabbed: General, Brand & Tokens, Formats, Prompts (DB-backed system prompt editing)
- [x] Templates page — grid with iframe previews
- [x] Assets page — generation card grid with thumbnails
- [x] Tasks page — filterable list with cancel/retry
- [x] Confirmation dialogs for all destructive actions

### Phase 8: Deployment + Polish (Completed / In Progress)
- [x] Production Docker Compose configuration
- [x] Seed script (`scripts/seed.py` for default formats, prompts, settings)
- [x] Full test suite (`pytest` backend test coverage)
- [x] Comprehensive documentation (`AGENTS.md`, `DESIGN.md`, `PLAN.md`, `README.md`)

### Phase 9: Design System Overhaul (Completed)
- [x] Removed `cdn.tailwindcss.com` (403 from server) — replaced with server-side CLI compilation
- [x] `tailwindcss` v4 standalone CLI included in Docker image
- [x] `_generate_theme_css()` — explicit DTCG path → CSS variable mapping (no more flattening collisions)
- [x] `color_tools.py` — `check_contrast()`, `generate_palette()` for light/dark themes
- [x] 11 LangChain `@tool`-decorated tools for design system generation
- [x] Token Generator agent (Dr. Soren Lindqvist) — LangGraph node with `bind_tools()`, WCAG AA validation
- [x] `check_contrast_tool` — validate any foreground/background pair
- [x] Socket.IO real-time progress (replaced polling + SSE)
- [x] `fix_brand_colors()` fixed — no longer strips `bg-primary` classes
- [x] `_resolve_tree()` fixed — passes root tree for cross-references
- [x] `_extract_semantic_colors()` fixed — walks full semantic tree
- [x] `_inject_defaults()` — color defaults removed (colors come from user tokens only)
- [x] Token generator prompt rewritten — dark-theme specific, explicit structure
- [x] Playground/test-suite routes (hidden from UI, accessible manually)
- [x] Test templates updated — use only Tailwind v4-guaranteed utilities, no fractional widths

### Phase 10: Visual Testing Playground (Completed)
- [x] `POST /playground/render-preview` — renders any template with any token set, returns HTML or PNG
- [x] `POST /playground/test-suite` — iterates ALL token sets × ALL templates, saves HTML+PNG per combination
- [x] `GET /playground/test-suite/{id}` — retrieve saved test suite results
- [x] 5 professional test templates (hero-quote, article-card, metrics-dashboard, minimal-list, split-layout)
- [x] 5 LLM-mock edge case templates (mixed styles, no-Tailwind, glass-dark, two-column, bold-minimal, data-viz)
- [x] 183 backend tests passing, all utility classes verified in compiled CSS
