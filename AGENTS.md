# Tasbir v3 — Agent Guide

## What We Are Building & Why

Tasbir is an AI-powered social media asset pipeline. Blog content goes in,
platform-optimized `.penpot` design files come out.

### The Problem We Solved

v2 had a multi-agent pipeline (6 agents: strategist, copywriter, visual director,
designer, quality check, token generator) that was producing inconsistent, low-quality
output. After a deep grilling session, we identified the root causes:

1. **Context pollution** — Every agent received ALL data as prose text.
   The LLM was flooded with irrelevant info (brand hex colors, design tokens,
   strategic briefs) that it had to parse and reinterpret. Information degraded
   at every handoff.

2. **No typed data flow** — Agents output unstructured markdown
   ("HEADLINE: some text"). Next agent parsed it back from text.
   Information was lost, hallucinated, or ignored.

3. **Design tokens were suggestions, not enforced** — The designer was told
   "use bg-primary" in a prompt hint, but the LLM often used
   `bg-blue-500` or `style="color: #333"`. The CSS system trying to fix
   this was fragile (regex replacements, Tailwind CLI dependency).

4. **Quality check was blind** — QC evaluated HTML text, not the actual
   rendered design. It parsed a "score" from LLM-generated markdown.
   Silent bad output passed through.

5. **Infrastructure bloat** — PostgreSQL, MinIO, SvelteKit UI, Socket.IO,
   Celery, Redis, Playwright. Many services, many moving parts.

### The New Architecture (v3)

**Core insight**: Design tokens live in Penpot (single source of truth).
The LLM never sees them. The pipeline generates `.penpot` files that humans
can open and edit in Penpot.

**Five-agent LangGraph pipeline**:
- **Strategist** (Aura Vance): content analysis → structured brief
- **Copywriter** (Julian Sterling): per-platform copy (typed JSON output)
- **Designer** (Marcus Chen): HTML with CSS variables (var(--color-*)), no brand colors
- **HTML→Penpot Converter** (programmatic, no LLM): Playwright DOM extraction → .penpot shapes
- **Verifier** (Victoria Thorne): multimodal audit — sees rendered image + knows design system

**Key principles**:
1. LLMs output **typed JSON** (not markdown). Pydantic models at every stage.
2. **Each agent gets only what it needs** — no context flooding.
3. **Design tokens are NEVER in LLM prompts** — injected programmatically.
4. **Penpot is the single source of truth** — tokens, templates, generated designs all live there.
5. **No Tailwind, no CSS frameworks** — Designer writes clean CSS with `var(--color-*)` variables.
6. **Verifier actually sees the design** — Gemini Vision on rendered PNG with design system context.
7. **Human-editable output** — `.penpot` files open in Penpot for tweaking.

### Current State (After Pruning)

**What was removed**:
- PostgreSQL (app data) → SQLite (2 tables: tasks + audit_logs)
- MinIO → .penpot files ARE the assets
- SvelteKit UI → n8n triggers pipeline, Penpot is the viewer
- Socket.IO → n8n polls REST API
- Tailwind CLI → no Tailwind in the system
- Prompt DB tables → YAML files in `config/prompts/`
- Templates/Brands/DesignTokens/Formats/Settings DB tables → all in Penpot `.penpot` file
- Ghost SDK → n8n handles Ghost webhooks
- Visual Director agent → merged into Designer + Penpot templates
- Token Generator agent → Penpot-native token management
- All 11 LangChain tools (check_contrast, search_unsplash, generate_background, etc.)

**What remains — working**:
- FastAPI (`POST /generate`, `GET /tasks/{id}`, `GET /health`)
- Celery + Redis task queue
- SQLite task tracking (GenerationTask + AuditLog models)
- LangGraph skeleton (graph.py, state.py — stubs, not implemented)
- Playwright service (for Phase 4 DOM extraction)
- Penpot Docker service (user opens designs here)
- YAML prompt configs (`config/prompts/*.yaml`)
- LLM client (Gemini 3.5 Flash Lite via OpenRouter fallback)

**What needs to be built (Phase 4)**:
- Actual agent node implementations (strategist, copywriter, designer)
- `.penpot` file reader/writer (`penpot_io.py`)
- HTML→Penpot converter (Playwright DOM extraction → .penpot shapes)
- KaTeX → SVG + Mermaid → SVG renderers
- Multimodal Verifier (Gemini Vision on rendered PNG)
- Design System .penpot file with tokens + templates

### Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (Python) |
| Task Queue | Celery + Redis |
| Pipeline | LangGraph (5 nodes) |
| LLM | Gemini 3.5 Flash Lite (free tier) |
| DOM Extraction | Playwright (headless Chromium) |
| Design Tool | Penpot (self-hosted, Docker) |
| Database | SQLite (aiosqlite) |
| Workflow | n8n (triggers from Ghost CMS) |

### Cost Target

Zero API costs:
- Gemini 3.5 Flash Lite free tier
- CSS backgrounds (no Unsplash unless free tier works)
- Self-hosted Penpot
- No SaaS dependencies

## Project Identity

- **Name**: Tasbir ("depiction" in Arabic)
- **Purpose**: AI-powered social media asset pipeline that outputs Penpot-native `.penpot` files
- **Stack**: Python (FastAPI, LangGraph, Celery) + Docker + Penpot
- **Storage**: SQLite (tasks/audit) + `.penpot` files (designs, tokens, templates)

## Architecture Overview

```
n8n Webhook → FastAPI (POST /generate) → Celery Worker → LangGraph Pipeline → .penpot file
                  │                                                        │
            GET /tasks/{id}                                    User opens in Penpot
            (n8n polls status)                                  (edit, review, save as template)
```

### Pipeline (5 Multi-Agent Nodes)

```
START
  │
  ▼
Strategist → analyzes content, produces structured brief (1 LLM call)
  │
  ▼
Copywriter → per-platform parallel (Send fan-out), produces structured copy
  │           (Semaphore controls concurrent LLM calls)
  ▼
Designer → per-platform parallel (Send fan-out)
  │         Input: copy + template from Penpot Design System file
  │         Output: HTML document with CSS variables (var(--color-*), NOT brand hex values)
  │         Template path: fills text slots in pre-built layout
  │         Custom path: creates HTML from scratch when no template fits
  │
  ▼
HTML→Penpot → per-platform (PROGRAMMATIC, no LLM)
  │           1. Playwright loads HTML → extracts computed DOM tree
  │           2. Maps DOM elements → .penpot shape types (frame, text, svg-raw, image)
  │           3. Resolves CSS variables → actual token values from design system
  │           4. Math: KaTeX → SVG → svg-raw shape | Diagrams: Mermaid → SVG → svg-raw
  │           5. Builds valid .penpot ZIP file
  │
  ▼
Verifier → per-platform (multimodal LLM call)
  │         Input: rendered PNG (from SVG), design system context, target platform
  │         Output: {pass, score, issues, critique}
  │
  ├── [pass] → END (success, .penpot file ready)
  └── [fail + retry < 2] → loop back to Designer with critique as additional context
```

## Agent Personas & Responsibilities

All agent prompts are stored in `backend/config/prompts/*.yaml`. Each agent outputs **typed, validated JSON** (not markdown prose). No agent receives another agent's raw output as text — the LangGraph state holds structured Pydantic models.

| Agent | Persona | What It Does | What It DOESN'T See |
|-------|---------|-------------|---------------------|
| **Strategist** | Aura Vance | Analyzes source content + target platforms → structured strategic brief | Brand colors, design tokens, format dimensions |
| **Copywriter** | Julian Sterling | Per-platform structured copy (headline, subhead, body, tagline, badge) | Brand colors, design tokens, raw content |
| **Designer** | Marcus Chen | Creates HTML document with CSS variables (var(--color-*)), clean layout | Brand hex values, token names — just CSS variables |
| **Verifier** | Victoria Thorne | Multimodal audit: sees rendered image, knows design system, judges quality | Nothing — sees everything (image + tokens) for informed critique |

## Core System Directives & Constraints

### 1. Penpot-Native Output
- Pipeline outputs a `.penpot` file (ZIP + JSON + embedded SVGs)
- User opens in Penpot to view, edit, promote designs
- No PNG assets stored — export from Penpot if needed

### 2. Strict No-Emoji Rule
- Raw Unicode emojis forbidden in copy and designs
- Enforced via system prompts (Designer, Copywriter)

### 3. Clean HTML, No Tailwind
- Designer writes plain HTML + CSS with CSS variables
- NO Tailwind classes (removed from entire system)
- NO raw brand hex colors — use `var(--color-*)` exclusively
- Math: `<span class="math">KaTeX</span>`
- Diagrams: `<div class="diagram">Mermaid</div>`

### 4. Design Tokens Are NEVER in LLM Prompts
- The LLM writes `var(--color-bg)` not `#0f172a`
- The HTML→Penpot converter resolves CSS variables to actual values from the Design System `.penpot` file
- Token names are predetermined (see Token Variable Reference below)

### 5. Typed, Structured Outputs
- Every agent outputs JSON matching a schema
- LangGraph state uses Pydantic models
- No markdown parsing, no "extract HEADLINE: from text"

### 6. Intra-Node Format Concurrency
- Copywriter and Designer process multiple platforms in parallel
- `asyncio.gather()` with Semaphores to respect rate limits
- HTML→Penpot converter runs per-platform (no LLM, fast)

## Design System & Template File

### Single `.penpot` File: `data/design_system/Tasbir Design System.penpot`

```
Tasbir Design System.penpot (ZIP)
├── manifest.json
├── files/{file-id}.json                ← File metadata
├── files/{file-id}/
│   ├── tokens.json                     ← ALL design tokens (colors, fonts, spacing)
│   ├── pages/
│   │   ├── instagram-square/           ← Page = platform format (1080×1080)
│   │   │   ├── Board "Modern Blog"     ← Template board with {{headline}}, {{body}} text layers
│   │   │   ├── Board "Bold Typo"
│   │   │   └── Board "Minimal Card"
│   │   ├── instagram-portrait/          ← 1080×1350
│   │   │   └── [template boards...]
│   │   ├── linkedin-post/               ← 1200×627
│   │   │   └── [template boards...]
│   │   └── twitter-card/                ← 1200×675
│   │       └── [template boards...]
│   ├── colors/                          ← Library color styles
│   ├── typographies/                    ← Library typography styles
│   └── components/                      ← Shared components
└── objects/                             ← Embedded images/SVGs
```

### Token Variable Reference (CSS Variable → Penpot Token Path)

| CSS Variable | Penpot Token Path | Example |
|---|---|---|
| `var(--color-bg)` | `color.semantic.bg.default` | `#0f172a` |
| `var(--color-bg-secondary)` | `color.semantic.bg.secondary` | `#1e293b` |
| `var(--color-text)` | `color.semantic.text.primary` | `#ffffff` |
| `var(--color-text-secondary)` | `color.semantic.text.secondary` | `#94a3b8` |
| `var(--color-primary)` | `color.brand.primary.main` | `#667eea` |
| `var(--color-secondary)` | `color.brand.secondary.main` | `#764ba2` |
| `var(--color-accent)` | `color.brand.accent` | `#6366f1` |
| `var(--color-border)` | `color.semantic.border` | `#334155` |
| `var(--font-sans)` | `typography.fontFamily.sans` | `Inter, sans-serif` |
| `var(--font-serif)` | `typography.fontFamily.serif` | `Instrument Serif` |
| `var(--font-mono)` | `typography.fontFamily.mono` | `JetBrains Mono` |
| `var(--radius-sm)` | `borderRadius.sm` | `4px` |
| `var(--radius-md)` | `borderRadius.md` | `8px` |
| `var(--shadow-md)` | `boxShadow.md` | `0 4px 6px rgba(...)` |

## Directory Structure

```
tasbir/
├── PLAN.md                              ← Project plan & phases
├── AGENTS.md                            ← This file
├── DESIGN.md                            ← Architecture decisions
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   │
│   ├── config/
│   │   └── prompts/
│   │       ├── strategist.yaml          ← Aura Vance prompt
│   │       ├── copywriter.yaml          ← Julian Sterling prompt
│   │       ├── designer.yaml            ← Marcus Chen prompt
│   │       └── verifier.yaml            ← Victoria Thorne prompt
│   │
│   ├── data/
│   │   ├── design_system/
│   │   │   └── Tasbir Design System.penpot
│   │   └── output/{task_id}/            ← Generated .penpot files
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      ← FastAPI app entry
│   │   ├── config.py                    ← Pydantic Settings (env-based)
│   │   │
│   │   ├── api/
│   │   │   ├── health.py                ← GET /health
│   │   │   ├── generate.py              ← POST /generate
│   │   │   └── tasks.py                 ← GET /tasks/{id}
│   │   │
│   │   ├── agents/
│   │   │   ├── graph.py                 ← LangGraph pipeline (5 nodes)
│   │   │   ├── state.py                 ← GenerationState + Pydantic models
│   │   │   ├── prompts.py              ← YAML prompt loader
│   │   │   ├── nodes/
│   │   │   │   ├── strategist.py        ← LLM node
│   │   │   │   ├── copywriter.py        ← LLM node
│   │   │   │   ├── designer.py          ← LLM node
│   │   │   │   ├── html_to_penpot.py    ← PROGRAMMATIC node
│   │   │   │   └── verifier.py          ← Multimodal LLM node
│   │   │   └── templates/
│   │   │       └── index.html           ← Fallback HTML wrapper (optional)
│   │   │
│   │   ├── services/
│   │   │   ├── llm.py                   ← Gemini/OpenRouter client
│   │   │   ├── penpot_io.py             ← .penpot file reader/writer
│   │   │   ├── dom_extractor.py         ← Playwright DOM extraction
│   │   │   ├── math_renderer.py         ← KaTeX → SVG converter
│   │   │   └── diagram_renderer.py      ← Mermaid → SVG converter
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py              ← Base + model imports
│   │   │   ├── task.py                  ← GenerationTask
│   │   │   └── audit_log.py             ← AuditLog
│   │   │
│   │   ├── db/
│   │   │   ├── session.py               ← SQLite async engine
│   │   │   └── repositories/
│   │   │       ├── tasks.py
│   │   │       └── audit_logs.py
│   │   │
│   │   ├── tasks/
│   │   │   ├── celery_app.py            ← Celery config
│   │   │   └── generate.py              ← Celery task
│   │   │
│   │   └── core/
│   │       ├── dependencies.py          ← FastAPI deps
│   │       └── security.py              ← API key verification
│   │
│   └── tests/
│       ├── test_api/                    ← Route tests
│       ├── test_agents/                 ← Graph & node tests
│       └── test_services/               ← Service tests
```

## Common Tasks For AI Agents

### Adding a new platform (format)
1. Add a new page to `data/design_system/Tasbir Design System.penpot` named after the platform (e.g., `facebook-post`)
2. Add template boards inside that page
3. Update `DEFAULT_FORMAT_DIMS` in `backend/app/services/formats.py`

### Adding a new agent
1. Create YAML prompt in `backend/config/prompts/{agent}.yaml`
2. Create Pydantic I/O models in `backend/app/agents/state.py`
3. Create node in `backend/app/agents/nodes/{agent}.py`
4. Register in `backend/app/agents/graph.py`

### Editing agent prompts
Edit the YAML files in `backend/config/prompts/`. No code changes needed.
Restart the worker to pick up changes.

### Adding a new token variable
1. Add the token to `tokens.json` inside the Design System `.penpot` file
2. Update the CSS variable → token mapping in `backend/app/agents/nodes/html_to_penpot.py`
3. Document the new variable in AGENTS.md Token Variable Reference table

### Testing
```bash
cd backend && .venv/bin/python -m pytest
```

## .penpot File Format Reference

The `.penpot` format is a ZIP archive containing JSON metadata + binary assets.
Full schema: https://help.penpot.app/technical-guide/developer/data-model/penpot-file-format/

### Shape Types Used

| Type | Purpose |
|------|---------|
| `frame` | Container/board/div |
| `text` | Text layer with font properties |
| `rect` | Rectangle with fills/borders |
| `svg-raw` | SVG embedded as vector (math, diagrams) |
| `image` | Raster image |
| `group` | Grouped shapes |

### Key Shape Attributes

```json
{
  "id": "uuid",
  "name": "Layer Name",
  "type": "frame|text|rect|svg-raw|image|group",
  "x": 0, "y": 0, "width": 1080, "height": 1080,
  "fills": [{"color": "#hex", "opacity": 1}],
  "strokes": [],
  "shadow": [],
  "blendMode": "normal",
  "opacity": 1,
  "shapes": []  // child shapes (for frame/group)
}
```

### Text Shape

```json
{
  "type": "text",
  "content": {
    "type": "root",
    "children": [{"text": "Hello", "fontFamily": "Inter", "fontSize": "48", ...}]
  }
}
```

### SVG Raw Shape

```json
{
  "type": "svg-raw",
  "content": "<svg xmlns='http://www.w3.org/2000/svg'>...</svg>"
}
```

## HTML → Penpot Converter Design

### DOM Element → Penpot Shape Mapping

| HTML Element | Penpot Shape | Notes |
|---|---|---|
| `<body>`, root `<div>` | `frame` (board) | Canvas-sized container |
| `<div>` with children | `frame` | Nested container |
| `<h1>`-`<h6>`, `<p>`, `<span>` | `text` | Resolves computed font properties |
| `<img src="...">` | `image` | Embeds image in objects/ |
| `<span class="math">` | `svg-raw` | KaTeX rendered SVG |
| `<div class="diagram">` | `svg-raw` | Mermaid rendered SVG |
| `<div>` with background | `rect` | Leaf with fill |

### CSS Variable Resolution

1. Playwright renders HTML → browser computes all CSS properties
2. DOM extractor reads computed styles (final values, already resolved)
3. If a property is `var(--color-bg)`, the browser resolves it to the fallback or inherited value
4. Post-extraction: we can optionally re-resolve to the Penpot token value

## API Endpoints

### POST /generate
```json
{
  "content": "Full article text...",
  "title": "Article Title",
  "platforms": ["instagram-square", "linkedin-post"],
  "webhook_url": "https://n8n.yourdomain.com/callback"   // optional
}
```
Response: `{"task_id": "uuid", "status": "pending"}`

### GET /tasks/{id}
Response:
```json
{
  "task_id": "uuid",
  "status": "running|completed|failed",
  "penpot_file_path": "data/output/task-id/generated.penpot",
  "boards": {"instagram-square": "board-id", ...},
  "error": null
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `OPENROUTER_API_KEY` | No | — | Fallback LLM provider |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Celery broker |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///data/tasbir.db` | SQLite for task tracking |
| `API_KEYS` | No | — | Comma-separated API keys for auth |
| `LOG_LEVEL` | No | `info` | Logging level |
