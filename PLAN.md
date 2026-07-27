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

### Phase 11: Per-Format Streaming Pipeline (Planned — DO NOT BUILD YET)

**Problem**: Current pipeline batches ALL formats through each node sequentially. Format1 must wait for Format2, Format3 to finish designer before any of them enter quality_check. This means 0 results visible until ALL formats finish all nodes.

**Goal**: Each format should stream through the full pipeline independently (designer → quality_check → renderer), so rendered assets appear one-by-one as they complete.

#### Architecture Change

**Current** (batch per node):
```
State: { html_by_format: {fmt1, fmt2, fmt3} }
Graph: designer(all) → quality_check(all) → renderer(all)
```

**Target** (per-format stream):
```
State: { format_progress: {fmt1: "designing", fmt2: "waiting", fmt3: "waiting"} }
Fork per format into sub-graph: designer(fmt1) → QC(fmt1) → renderer(fmt1)
                                                  ↘ designer(fmt2) → QC(fmt2) → renderer(fmt2)
```

#### Implementation Tasks

1. **Restructure state** — Replace `html_by_format`, `assets_by_format` monolithic dicts with per-format entries that track each format's stage independently:
   ```python
   class GenerationState(TypedDict):
       format_tasks: dict[str, FormatTask]  # key=fmt_id
   
   class FormatTask(TypedDict):
       status: str  # waiting, copywriting, designing, qc, rendering, done, failed
       copy: str
       html: str
       png_url: str | None
       error: str | None
   ```

2. **Change graph topology** — Instead of 6 nodes in a line, use a **dynamic fan-out** with LangGraph's `Send` API:
   ```python
   def continue_pipeline(state):
       """After strategist/copywriter, fan out per format."""
       tasks = []
       for fmt in state["requested_formats"]:
           if fmt not in state["format_tasks"] or state["format_tasks"][fmt]["status"] == "waiting":
               tasks.append(Send("process_format", {"format_id": fmt, ...}))
       return tasks
   ```

3. **Subgraph per format** — Create a mini-pipeline subgraph that processes a single format through designer → quality_check → renderer:
   ```python
   format_pipeline = StateGraph(FormatTask)
   format_pipeline.add_node("designer", designer_node_single)
   format_pipeline.add_node("quality_check", quality_check_node_single)
   format_pipeline.add_node("renderer", renderer_node_single)
   format_pipeline.add_edge("designer", "quality_check")
   format_pipeline.add_conditional_edges("quality_check", after_quality)
   format_pipeline.add_edge("renderer", END)
   ```

4. **Progress reporting** — Emit `progress` events per format, not per node:
   ```python
   emitter.emit("format_progress", {
       "task_id": task_id,
       "format_id": fmt,
       "stage": "rendering",
       "url": png_url,  # present when done
   }, room=task_id)
   ```

5. **Frontend updates** — Listen for `format_progress` events and show per-format cards that transition from "Designing..." → "Auditing..." → "Rendering..." → done with thumbnail.

6. **Gemini rate limit management** — Semaphore across the ENTIRE format fan-out (not per-node) to ensure total concurrent LLM calls across all formats stays within free tier limits (e.g., global `Semaphore(2)` for all formats across all pipeline stages).

#### Risks & Considerations
- LangGraph's `Send()` API requires the subgraph to return results that merge back into parent state. Need to ensure `GenerationState` properly merges per-format results.
- If one format fails QC repeatedly, it should fail independently without blocking other formats.
- The fan-out adds complexity to the graph UI visualization — need to track per-format edges.

### Phase 12: Pipeline Graph Visualization Library (Planned — DO NOT BUILD YET)

**Problem**: Current `LangGraphVisualizer.svelte` is a hand-crafted SVG with 6 boxes and lines. It shows the pipeline stages but NOT per-format progress, NOT live state, and NOT edge animations.

**Goal**: Replace with a proper graph visualization that shows:
- All 6 main nodes (strategist → copywriter → visual_director → designer → quality_check → renderer)
- Per-format progress through each node (e.g., "Format 1: Rendering", "Format 2: QC", "Format 3: Designing")
- Live transitions with animated edges
- Pass/fail/retry indicators on quality_check loop

**Decision: Svelte Flow (`@xyflow/svelte`)** — Same team as React Flow, built for Svelte. Supports custom nodes, animated edges, interactive graphs, zoom/pan, responsive layouts. ~50KB gzipped.

#### Implementation Tasks

1. Add `dagre-d3` and `d3` to dependencies (`npm install dagre-d3 d3`)
2. Rewrite `LangGraphVisualizer.svelte`:
   - Define graph nodes (strategist, copywriter, visual_director, designer, quality_check, renderer) with fixed positions
   - Define edges between them
   - Color-code nodes by status (pending=dim, active=accent, completed=green, failed=red)
   - Animate active node with a pulsing highlight
   - Show per-format progress as labels/tags on nodes (e.g., "2/3 formats rendering")
   - Animate quality_check retry loop with dashed red edge
3. Add a "live timeline" view showing which formats completed and their rendering times
4. Keep responsive — collapse to compact view on mobile

#### Wireframe

```
[Strategist] ──→ [Copywriter] ──→ [Visual Director]
                                         │
                                         ▼
                                   [Designer] ──→ [Quality Check] ──→ [Renderer]
                                                       │  ↑                    │
                                                       │  │ (retry)            │
                                                       └──┘                    ▼
                                                                         [Done ✓]

Format 1: ✅ Renderer (2.3s)
Format 2: 🔄 Designer (1.2s)
Format 3: ⏳ Waiting
```
