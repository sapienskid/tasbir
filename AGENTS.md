# Tasbir v3 — Agent Guide

## What We Are Building & Why

Tasbir is an AI-powered social media asset pipeline. Blog content goes in,
platform-optimized HTML + PNG renders come out.

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

**Core insight**: Design tokens live in YAML files (single source of truth).
The LLM never sees them. The pipeline generates HTML files that Playwright
renders to PNG for visual verification.

**Four-agent LangGraph pipeline**:
- **Strategist** (Aura Vance): content analysis → structured brief
- **Copywriter** (Julian Sterling): per-platform copy (typed JSON output)
- **Designer** (Marcus Chen): HTML with CSS variables (var(--color-*)), no brand colors
- **Verifier** (Victoria Thorne): injects tokens/KateX/images, renders to PNG,
  multimodal audit via Gemini Vision

**Key principles**:
1. LLMs output **typed JSON** (not markdown). Pydantic models at every stage.
2. **Each agent gets only what it needs** — no context flooding.
3. **Design tokens are NEVER in LLM prompts** — injected programmatically after design.
4. **YAML is the single source of truth** — brand profile, design tokens, platform
   dimensions, and campaign presets all in `data/design_system/*.yaml`.
5. **No Tailwind, no CSS frameworks** — Designer writes clean CSS with `var(--color-*)` variables.
6. **Verifier actually sees the design** — Gemini Vision on rendered PNG with design system context.
7. **Human-editable output** — `.html` files open in any browser; `.png` files ready to share.

### Current State

**What works**:
- FastAPI (`POST /generate`, `GET /tasks/{id}`, `GET /health`)
- Celery + Redis task queue
- SQLite task tracking (GenerationTask + AuditLog models)
- LangGraph pipeline with 4 agent nodes
- Playwright service (HTML rendering + DOM extraction)
- YAML prompt configs (`config/prompts/*.yaml`)
- YAML design system (`data/design_system/*.yaml`)
- LLM client (Gemini 3.5 Flash Lite via OpenRouter fallback)
- KaTeX automatic injection for math rendering
- Image embedding (download, base64 encode, inject into HTML)
- Campaign presets (tone, visual_style, background, illustrations)

### Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (Python) |
| Task Queue | Celery + Redis |
| Pipeline | LangGraph (4 nodes) |
| LLM | Gemini 3.5 Flash Lite (free tier) |
| Rendering | Playwright (headless Chromium) |
| Database | SQLite (aiosqlite) |
| Workflow | n8n (triggers from Ghost CMS) |

### Cost Target

Zero API costs:
- Gemini 3.5 Flash Lite free tier
- CSS backgrounds (no Unsplash unless free tier works)
- No SaaS dependencies

## Project Identity

- **Name**: Tasbir ("depiction" in Arabic)
- **Purpose**: AI-powered social media asset pipeline that outputs HTML + PNG
- **Stack**: Python (FastAPI, LangGraph, Celery) + Docker + Playwright
- **Storage**: SQLite (tasks/audit) + `data/output/{task_id}/` (HTML, PNG)

## Architecture Overview

```
n8n Webhook → FastAPI (POST /generate) → Celery Worker → LangGraph Pipeline → HTML + PNG
                  │                                                        │
            GET /tasks/{id}                                     Files saved in data/output/{task_id}/
            (n8n polls status)                                  (.html for review, .png for sharing)
```

### Pipeline (4 Agent Nodes)

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
  │         Input: copy + strategic brief + brand info + campaign + images
  │         Output: HTML document with CSS variables (var(--color-*), NOT brand hex values)
  │
  ▼
Verifier → per-platform
  │         1. Injects design tokens as CSS :root variables
  │         2. Injects KaTeX CDN if `<span class="math">` detected
  │         3. Embeds base64 images
  │         4. Saves HTML to data/output/{task_id}/{fmt_id}.html
  │         5. Renders to PNG via Playwright
  │         6. Multimodal LLM audit on rendered PNG
  │         Output: {pass, score, issues, critique}
  │
  ├── [pass] → END (success, HTML + PNG ready)
  └── [fail + retry < 2] → loop back to Designer with critique as additional context
```

## Agent Personas & Responsibilities

All agent prompts are stored in `backend/config/prompts/*.yaml`. Each agent outputs **typed, validated JSON** (not markdown prose). No agent receives another agent's raw output as text — the LangGraph state holds structured Pydantic models.

| Agent | Persona | What It Does | What It DOESN'T See |
|-------|---------|-------------|---------------------|
| **Strategist** | Aura Vance | Analyzes source content + target platforms → structured strategic brief | Brand colors, design tokens, format dimensions |
| **Copywriter** | Julian Sterling | Per-platform structured copy (headline, subhead, body, tagline, badge) | Brand colors, design tokens, raw content |
| **Designer** | Marcus Chen | Creates HTML document with CSS variables (var(--color-*)), clean layout | Brand hex values, token names — just CSS variables |
| **Verifier** | Victoria Thorne | Injects tokens/KateX/images, renders to PNG, multimodal audit | Nothing — sees everything (image + tokens) for informed critique |

## Core System Directives & Constraints

### 1. HTML + PNG Output
- Pipeline saves HTML with injected tokens, KaTeX, and images
- Playwright renders a PNG screenshot for visual verification
- Output is `data/output/{task_id}/{format_id}.html` + `.png`

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
- The Verifier resolves CSS variables to actual values from `tokens.yaml`
- Token names are predetermined (see Token Variable Reference below)

### 5. Typed, Structured Outputs
- Every agent outputs JSON matching a schema
- LangGraph state uses Pydantic models
- No markdown parsing, no "extract HEADLINE: from text"

### 6. Intra-Node Format Concurrency
- Copywriter and Designer process multiple platforms in parallel
- `asyncio.gather()` with Semaphores to respect rate limits

### 7. Brand Context Flows Through Every Agent
- Brand name/tagline/mission/story passed to Strategist, Copywriter, Designer
- Campaign presets define tone, visual_style, background, illustrations
- Overrides (badge, tagline) from `brand.yaml` applied at Copywriter level

### 8. KaTeX Injected Automatically
- If Designer output contains `<span class="math">`, KaTeX CDN is injected
- No need for the LLM to manually include KaTeX scripts
- Mermaid diagrams (`<div class="diagram">`) are rendered by Playwright

## Design System Configuration

### YAML Files in `data/design_system/`

```
data/design_system/
├── brand.yaml              ← Brand identity (name, tagline, mission, story, social, overrides)
├── tokens.yaml             ← CSS variable → value mappings (colors, fonts, spacing, shadows)
├── platforms.yaml          ← Platform dimensions [width, height] in pixels
├── campaigns.yaml          ← Campaign presets (tone, visual_style, background, illustrations)
└── design-instruction.yaml ← Compositional constraints (grid, type scale, decoration rules)
```

### `brand.yaml`

```yaml
brand:
  name: "Your Brand"
  tagline: "Your tagline"
  mission: "Your mission statement"
  story: "Your brand story"
  url: "https://example.com"
  social:
    github: "username"
    twitter: "username"
    linkedin: "username"

overrides:
  badge: ""       # When set, used instead of LLM-generated badge
  tagline: ""     # When set, used instead of LLM-generated tagline
```

### `tokens.yaml`

```yaml
--color-bg: "#0a0a1a"
--color-bg-secondary: "#141428"
--color-text: "#e8e8f0"
--color-text-secondary: "#9494b8"
--color-primary: "#5b8def"
--color-secondary: "#7c6df0"
--color-accent: "#48c6ef"
--color-border: "#2a2a4a"
--font-sans: "Inter, system-ui, sans-serif"
--font-serif: "Merriweather, Georgia, serif"
--font-mono: "JetBrains Mono, Fira Code, monospace"
--radius-sm: "4px"
--radius-md: "8px"
--shadow-md: "0 4px 12px rgba(0,0,0,0.4)"
```

### `platforms.yaml`

```yaml
instagram-square: [1080, 1080]
instagram-portrait: [1080, 1350]
instagram-story: [1080, 1920]
linkedin-post: [1200, 627]
twitter-card: [1200, 675]
facebook-post: [1200, 630]
pinterest-pin: [1000, 1500]
```

### `campaigns.yaml`

```yaml
default:
  label: "Default"
  tone: "professional"
  visual_style: "clean editorial"
  background: "dark gradient"
  illustrations: "geometric accents"

educational:
  label: "Educational"
  tone: "warm professional"
  visual_style: "clean, readable, diagram-friendly"
  background: "dark with subtle grid"
  illustrations: "diagrams, code snippets, math"

product-launch:
  label: "Product Launch"
  tone: "energetic"
  visual_style: "bold minimal"
  background: "solid dark with accent glow"
  illustrations: "product mockup, logo"

thought-leadership:
  label: "Thought Leadership"
  tone: "sophisticated"
  visual_style: "editorial, serif-friendly"
  background: "dark premium"
  illustrations: "minimal, abstract shapes"

tutorial:
  label: "Tutorial"
  tone: "friendly technical"
  visual_style: "clean step-by-step"
  background: "dark with grid pattern"
  illustrations: "screenshots, code blocks, diagrams"
```

### `design-instruction.yaml`

```yaml
grid:
  columns: 12
  margin: "6%"
  gutter: "2%"
  baseline: "8px"
  max_violations: 1

type_scale:
  base: "16px"
  ratio: 1.333
  sizes_px: [12, 16, 21, 28, 38, 51, 68]
  weights:
    headline: [700, 800, 900]
    body: [400, 500]

decoration:
  unicode_symbols: false
  gradients_as_bg: false
  glassmorphism: false
  badges_pills: false
  max_border_radius: "4px"

images:
  default_crop: "sharp_rect"
  text_overlay_fade: "targeted"

math:
  dedicated_grid_block: true
```

## Token Variable Reference (CSS Variable → YAML Value)

| CSS Variable | Token Path (tokens.yaml) | Example Value |
|---|---|---|
| `var(--color-bg)` | `--color-bg` | `#0a0a1a` |
| `var(--color-bg-secondary)` | `--color-bg-secondary` | `#141428` |
| `var(--color-text)` | `--color-text` | `#e8e8f0` |
| `var(--color-text-secondary)` | `--color-text-secondary` | `#9494b8` |
| `var(--color-primary)` | `--color-primary` | `#5b8def` |
| `var(--color-secondary)` | `--color-secondary` | `#7c6df0` |
| `var(--color-accent)` | `--color-accent` | `#48c6ef` |
| `var(--color-border)` | `--color-border` | `#2a2a4a` |
| `var(--font-sans)` | `--font-sans` | `Inter, system-ui, sans-serif` |
| `var(--font-serif)` | `--font-serif` | `Merriweather, Georgia, serif` |
| `var(--font-mono)` | `--font-mono` | `JetBrains Mono, Fira Code, monospace` |
| `var(--radius-sm)` | `--radius-sm` | `4px` |
| `var(--radius-md)` | `--radius-md` | `8px` |
| `var(--shadow-md)` | `--shadow-md` | `0 4px 12px rgba(0,0,0,0.4)` |

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
│   │   │   ├── brand.yaml              ← Brand identity
│   │   │   ├── tokens.yaml             ← Design tokens (CSS vars)
│   │   │   ├── platforms.yaml          ← Platform dimensions
│   │   │   ├── campaigns.yaml          ← Campaign presets
│   │   │   └── design-instruction.yaml ← Compositional constraints (grid, type scale, decoration rules)
│   │   └── output/{task_id}/           ← Generated HTML + PNG files
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      ← FastAPI app entry
│   │   ├── config.py                    ← Pydantic Settings (env-based)
│   │   │
│   │   ├── api/
│   │   │   ├── health.py                ← GET /health
│   │   │   ├── generate.py              ← POST /generate
│   │   │   └── tasks.py                 ← GET /tasks/{id}, DELETE
│   │   │
│   │   ├── agents/
│   │   │   ├── orchestrator/
│   │   │   │   ├── graph.py             ← LangGraph pipeline (4 nodes)
│   │   │   │   ├── state.py             ← GenerationState + Pydantic models
│   │   │   │   └── nodes/
│   │   │   │       ├── strategist.py    ← LLM node
│   │   │   │       ├── copywriter.py    ← LLM node (parallel)
│   │   │   │       ├── designer.py      ← LLM node (parallel)
│   │   │   │       ├── quality_check.py ← Verifier (render + multimodal)
│   │   │   │       └── renderer.py      ← HTML persistence (tokens/KateX/images)
│   │   │   └── prompts/
│   │   │       └── registry.py          ← YAML prompt loader
│   │   │
│   │   ├── services/
│   │   │   ├── llm.py                   ← Gemini/OpenRouter client
│   │   │   ├── tokens.py                ← Token/brand/campaign/platform YAML loader
│   │   │   ├── formats.py               ← Format dimension helper
│   │   │   ├── image_loader.py          ← Image download + base64 embed
│   │   │   ├── dom_extractor.py         ← Playwright DOM extraction client
│   │   │   ├── renderer.py              ← Playwright PNG render client
│   │   │   └── render_server.py         ← Playwright HTTP microservice (Docker)
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
│   │   │   └── generate.py              ← Celery task (loads config, runs pipeline)
│   │   │
│   │   └── core/
│   │       ├── dependencies.py          ← FastAPI deps
│   │       ├── security.py              ← API key verification
│   │       ├── errors.py                ← Error handling
│   │       └── logging.py               ← Logging config
│   │
│   └── tests/
│       ├── test_api/                    ← Route tests
│       ├── test_agents/                 ← Graph & node tests
│       └── test_services/               ← Service tests
```

## Common Tasks For AI Agents

### Adding a new platform (format)
1. Add `platform-id: [width, height]` to `data/design_system/platforms.yaml`
2. No code changes needed — dimensions are loaded dynamically

### Adding a new campaign preset
1. Add a new key to `data/design_system/campaigns.yaml`
2. Set tone, visual_style, background, illustrations
3. Reference by name in API: `"campaign": "educational"`

### Adding a new agent
1. Create YAML prompt in `backend/config/prompts/{agent}.yaml`
2. Create Pydantic I/O models in `backend/app/agents/orchestrator/state.py`
3. Create node in `backend/app/agents/orchestrator/nodes/{agent}.py`
4. Register in `backend/app/agents/orchestrator/graph.py`

### Editing agent prompts
Edit the YAML files in `backend/config/prompts/`. No code changes needed.
Restart the worker to pick up changes.

### Adding a new token variable
1. Add `--variable-name: "value"` to `data/design_system/tokens.yaml`
2. Add the CSS variable reference to the Designer's CSS_VARS_REFERENCE in `backend/app/agents/orchestrator/nodes/designer.py`
3. Add default value to `DEFAULT_TOKEN_VALUES` in `backend/app/services/tokens.py`
4. Document the new variable in AGENTS.md Token Variable Reference table

### Overriding copy fields
1. Set `overrides.headline`, `overrides.subhead`, etc. in the API request
2. Or set `overrides.badge` / `overrides.tagline` in `brand.yaml`
3. Copywriter applies overrides before calling LLM

### Modifying design-instruction.yaml (grid, type scale, decoration rules)
1. Edit values in `data/design_system/design-instruction.yaml`
2. No code changes needed — loaded dynamically by the designer node
3. Restart the worker to pick up changes

### Adding embedded images
1. Include `images` array in POST /generate request
2. Each image: `{url, alt, description, placement}`
3. Placement options: `auto`, `background`, `top-left`, `center`, `bottom-right`

### Testing
```bash
cd backend && .venv/bin/python -m pytest
```

## API Endpoints

### POST /generate
```json
{
  "content": "Full article text...",
  "title": "Article Title",
  "url": "https://example.com/article",
  "excerpt": "Short summary...",
  "tags": ["ai", "math"],
  "platforms": ["instagram-square", "linkedin-post"],
  "campaign": "default",
  "overrides": {
    "headline": "Custom Headline"
  },
  "images": [
    {
      "url": "https://example.com/image.png",
      "alt": "Description",
      "description": "Place this near the headline",
      "placement": "auto"
    }
  ],
  "webhook_url": "https://n8n.yourdomain.com/callback"
}
```
Response: `{"task_id": "uuid", "status": "pending"}`

### GET /tasks/{id}
Response:
```json
{
  "id": "uuid",
  "status": "running|completed|failed",
  "source_data": { ... },
  "result": {
    "output_paths": {
      "html": "data/output/task-id/instagram-square.html",
      "png": "data/output/task-id/instagram-square.png"
    },
    "strategic_brief": { ... },
    "platforms": {
      "instagram-square": {
        "status": "verified",
        "quality_score": 85,
        "quality_issues": [],
        "html_path": "data/output/task-id/instagram-square.html"
      }
    }
  },
  "error": null
}
```

### GET /health
Response: `{"status": "ok"}`

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `OPENROUTER_API_KEY` | No | — | Fallback LLM provider |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Celery broker |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///data/tasbir.db` | SQLite for task tracking |
| `API_KEYS` | No | — | Comma-separated API keys for auth |
| `LOG_LEVEL` | No | `info` | Logging level |
