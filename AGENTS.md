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

**Five-agent LangGraph pipeline**:
- **Strategist** (Aura Vance): content analysis → structured brief
- **Planner** (Aria Sol): post structure (single/carousel/story, ratio, slide count) — hybrid: LLM only when structure is undecided (`platforms:["auto"]` or unpinned carousel slides/ratio), else deterministic
- **Copywriter** (Julian Sterling): per-platform copy (typed JSON output)
- **Designer** (Marcus Chen): HTML with CSS variables (var(--color-*)), no brand colors
- **Verifier** (Victoria Thorne): injects tokens/KateX/images, renders to PNG,
  multimodal audit via Gemini Vision

**Key principles**:
1. LLMs output **typed JSON** (not markdown). Pydantic models at every stage.
2. **Each agent gets only what it needs** — no context flooding.
3. **Design tokens are NEVER in LLM prompts** — injected programmatically after design.
4. **The database is the single source of truth** — brand, tokens, campaigns,
   design-instruction, platforms, curated fonts, templates, agents, and runtime
   tuning knobs are all DB-backed and Studio-editable. The `data/design_system/*.yaml`
   files only **seed** first boot (seed-once; the Studio owns the rows after).
5. **No Tailwind, no CSS frameworks** — Designer writes clean CSS with `var(--color-*)` variables.
6. **Verifier actually sees the design** — Gemini Vision on rendered PNG with design system context.
7. **Human-editable output** — `.html` files open in any browser; `.png` files ready to share.

### Current State

**What works**:
- FastAPI (`POST /generate`, `GET /tasks/{id}`, `GET /health`, file delivery, re-render)
- Celery + Redis task queue (+ hourly `retention.sweep_expired` beat)
- SQLite task tracking (GenerationTask + AuditLog models)
- LangGraph pipeline (strategist → planner → copywriter → process_all_formats)
- Playwright service (HTML rendering + DOM extraction + overflow detection, internal-only + shared-secret auth)
- YAML prompt configs (`config/prompts/*.yaml`)
- **DB-backed design systems** (v0.5): brand, footer, categories, campaigns,
  tokens, design-instruction, logo — fully editable in the Studio
- **DB-backed platforms / curated fonts / runtime settings** (v3.6): platform
  dimensions, the Google Fonts pool, and pipeline tuning knobs (verifier
  retries, copywriter concurrency, vision interval, chat cap, template
  anti-repeat) are all seed-once tables editable in the Studio Settings page
- **DB-backed template library** (v0.5): 16 seeded templates + AI-generated
  ones, scoped per design system, template-first pipeline with LLM fallback
- **Brand Builder agent**: form + optional reference/logo images → complete
  design system + starter templates (background Celery job)
- **Template Author agent**: mockup image → validated Jinja2 template
- YAML design system (`data/design_system/*.yaml`) — seeds the `default`
  system on first boot; templates' YAML catalog only used for that seed
- LLM client (Gemini 3.5 Flash Lite via OpenRouter fallback)
- KaTeX automatic injection for math rendering
- Image embedding (SSRF-guarded download, base64 encode, inject into HTML)
- Campaign presets (tone, ground, language) + category taxonomy
- Deterministic QC: emoji/hex/footer/category/display-face/canvas checks + DOM overflow
- Deterministic font loading (auto-quoted families, `document.fonts.ready`)
- Security hardening: fail-closed API keys, per-key Redis rate limit, SSRF guard, HTML sanitizer, input caps
- Ephemeral artifact delivery (persist-until-TTL + `?consume=true` opt-in delete)
- Manual edit → re-render endpoint (`POST /tasks/{id}/formats/{fmt}/rerender`)
- **Agent chat** (`GET/POST /tasks/{id}/chat`): DB-backed thread per (task, format);
  vision-capable design assistant proposes replacement HTML, applied review-then-render
- **Visual editing** in the Studio: locked-down GrapesJS canvas (exact format dims,
  no manual blocks — elements come from the agent), apply → re-render
- Bulk download of all artifacts as a ZIP (`GET /tasks/{id}/files/archive`)
- **Template library**: human-authored Jinja2 post compositions (12), template-first
  pipeline with LLM fallback, category-mapped selection + strategist `template_hint`,
  anti-repeat via Redis, and a promote-edited-post learning loop
- **Tasbir Studio**: React + Vite + shadcn/ui SPA served by FastAPI (Monaco + GrapesJS editors,
  live scaled preview, inspector rail with QC + agent chat, bulk ZIP download, save-as-template)

### Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (Python) |
| Task Queue | Celery + Redis (worker + beat) |
| Pipeline | LangGraph (3 nodes + per-format chain) |
| LLM | Gemini 3.5 Flash Lite (free tier) |
| Rendering | Playwright (headless Chromium, slim image, internal network) |
| Database | SQLite (aiosqlite, create_all on boot) |
| Frontend | React 19 + Vite + shadcn/ui + SWR + Monaco (Tasbir Studio) |
| Workflow | n8n (triggers from Ghost CMS) |

### Cost Target

Zero API costs:
- Gemini 3.5 Flash Lite free tier
- CSS backgrounds (no Unsplash unless free tier works)
- No SaaS dependencies

## Project Identity

- **Name**: Tasbir ("depiction" in Arabic)
- **Purpose**: AI-powered social media asset pipeline that outputs HTML + PNG
- **Stack**: Python (FastAPI, LangGraph, Celery) + React (Vite/shadcn) + Docker + Playwright
- **Storage**: SQLite (tasks/audit) + `data/output/{task_id}/` (HTML, PNG, ephemeral)

## Architecture Overview

```
n8n Webhook → FastAPI (POST /generate) → Celery Worker → LangGraph Pipeline → HTML + PNG
                  │                                                        │
            GET /tasks/{id}                              Files saved in data/output/{task_id}/
            (n8n polls status)                           (.html for review, .png for sharing)
                  │                  files persist until the TTL sweep; ?consume=true deletes on download
            Tasbir Studio (React SPA, same origin) ── POST /tasks/{id}/formats/{fmt}/rerender
            edit HTML → re-render → preview + QC
```

### Pipeline (5 Agent Nodes)

```
START
  │
  ▼
Strategist → analyzes content, produces structured brief + category + ground (1 LLM call)
  │
  ▼
Planner → post structure (single/carousel/story, ratio, slides) — LLM only when
  │        undecided ("auto" platforms / unpinned carousel slides+ratio),
  │        else deterministic PostPlan (0 extra calls)
  ▼
Copywriter → per-platform parallel (asyncio.gather + Semaphore), structured copy
  │
  ▼
process_all_formats → per-platform, in parallel via asyncio.gather:
  │        Each format runs an isolated branch:
  │
  │        Designer → Input: copy + brief + ground + category + footer + images
  │        │           + a deterministic layout archetype (composition varies per post)
  │        │         Output: HTML with CSS variables (var(--color-*), NOT brand hex)
  │        │
  │        Renderer → injects tokens (auto-quoted font families), Google Fonts
  │        │           link, KaTeX CDN, base64 images; saves {fmt_id}.html
  │        │
  │        Verifier  → 1. deterministic checks (emoji, raw hex, footer, category,
  │        │             display face, canvas size) — hard fail on violation
  │        │             2. renders to PNG via Playwright (waits for fonts)
  │        │             3. DOM-based overflow check — hard fail + retry
  │        │             4. multimodal LLM audit on rendered PNG
  │        │             Output: {pass, score, issues, critique}
  │        │
  │        └── [pass] → branch done
  │            [fail + retry < 2] → loop back to Designer with critique
  │
  ▼
sequence_check → carousels: deterministic (same dims, i/N counter) + opt-in
  │             vision set-pass (sequence_audit)
  ▼
END (success, HTML + PNG per format ready)
```

Each format branch merges its slice back deterministically (no reducer races),
so the final state always reflects every format's real status.

## Agent Personas & Responsibilities

All agent prompts are stored in `backend/config/prompts/*.yaml`. Each agent outputs **typed, validated JSON** (not markdown prose). No agent receives another agent's raw output as text — the LangGraph state holds structured Pydantic models.

| Agent | Persona | What It Does | What It DOESN'T See |
|-------|---------|-------------|---------------------|
| **Strategist** | Aura Vance | Analyzes source content + target platforms → structured strategic brief | Brand colors, design tokens, format dimensions |
| **Planner** | Aria Sol | Decides post structure (single/carousel/story, ratio, slides, per-slide outline) — hybrid gating, user intent wins | Brand colors, design tokens, raw content |
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
- Campaign presets define tone, ground, and verbal language
- Overrides (badge, tagline, category) from `brand.yaml` applied at the Copywriter/Strategist level

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
├── campaigns.yaml          ← Campaign presets (tone, ground, language)
└── design-instruction.yaml ← Swiss style rules (palette, type scale, spacing, formats)
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

# Footer row — rendered on every post (bottom-anchored, hairline rule above).
footer:
  left: "SABIN POKHAREL"
  right: "@SAPIENSKID"

# Approved category labels — every post has exactly one. Optional per-category
# "ground" reserves black-ground for that category.
categories:
  - name: "PORTFOLIO"
    description: "Project posts"
  - name: "PROJECT"
    description: "Individual build/ship updates"
  - name: "WRITING"
    description: "Blog posts"
  - name: "THE LIMITS No.{issue}"
    description: "Newsletter posts — substitute the real issue number"
  - name: "NOTE"
    description: "Short-form/thought posts"
    ground: "black"

overrides:
  badge: ""       # When set, used instead of LLM-generated badge
  tagline: ""     # When set, used instead of LLM-generated tagline
  category: ""    # When set, forces this exact category label
```

### `tokens.yaml`

```yaml
--color-bg: "#FFFFFF"
--color-bg-inverted: "#000000"
--color-text: "#000000"
--color-text-inverted: "#FFFFFF"
--color-text-secondary: "#6E6E6E"
--color-text-tertiary: "#B0B0B0"
--color-border: "#D9D9D9"
--color-border-inverted: "#2A2A2A"
--font-sans: "Inter, 'Helvetica Neue', Arial, sans-serif"
--font-display: "Space Grotesk, Inter, sans-serif"
--font-serif: "Source Serif 4, Georgia, serif"
--radius-sm: "0px"
--radius-md: "0px"
--shadow-md: "none"
```

Strictly grayscale (Swiss monochrome). Two grounds: white (`--color-bg`) and
black (`--color-bg-inverted`). No hue, ever. The verifier exposes these values;
the designer only ever sees variable NAMES + semantic roles.

### `platforms.yaml`

```yaml
instagram-square: [1080, 1080]
instagram-carousel: [1080, 1080]
instagram-carousel-portrait: [1080, 1350]
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
  ground: "white"
  language: "clean editorial, weight-and-size hierarchy, generous whitespace"

educational:
  label: "Educational"
  tone: "warm professional"
  ground: "white"
  language: "clean, readable, math-friendly, generous whitespace"

thought-leadership:
  label: "Thought Leadership"
  tone: "sophisticated"
  ground: "black"
  language: "editorial, generous whitespace, quiet confidence"
```

Campaigns set tone, ground (white | black — the only two allowed backgrounds),
and verbal language guidance. Ground priority: campaign → category → white.

### `design-instruction.yaml`

```yaml
style:
  palette: "monochrome"
  allowed_grounds: ["white", "black"]
  default_ground: "white"
  max_weights_per_family: 2
  shadows: false
  border_radius: "0px"
  illustrations: false
  gradients: false

type_voice:
  display: "Space Grotesk (var(--font-display)) is the signature display voice — headline + footer wordmark ONLY"
  serif: "Source Serif 4 (var(--font-serif)) is the editorial text voice — subhead + body copy"
  body: "Inter (var(--font-sans)) is the quiet interface voice — category, metadata, handle"

type_scale:
  base_canvas_width: 1080
  roles:
    category:  {family: sans,    size: 22, weight: 500, tracking: "0.12em", case: "uppercase"}
    headline:  {family: display, size: 76, weight: 700, tracking: "-0.01em", case: "sentence", line_height: 1.0, max_lines: {square: 4, landscape: 3}}
    subhead:   {family: serif,   size: 36, weight: 400, case: "sentence", measure_px: 600}
    body:      {family: serif,   size: 28, weight: 400, case: "sentence", min_size: 24, measure_px: 600}
    metadata:  {family: sans,    size: 20, weight: 500, tracking: "0.08em", case: "uppercase"}

spacing:
  unit: 8
  scale: [8, 16, 24, 32, 48, 64, 96, 128]
  margin: 64
  margin_story_vertical: 160

format_families:
  instagram-square: square
  instagram-portrait: portrait
  instagram-story: story
  linkedin-post: landscape
  twitter-card: landscape
  facebook-post: landscape
  pinterest-pin: portrait

footer:
  enabled: true
  rule: "1px hairline"
  gap: 24
  style: "metadata"
  wordmark: {family: display, size: 24, weight: 500, tracking: "-0.01em", case: "uppercase"}

do_dont:
  do: ["Left-align everything, always", "THREE voices: display (Space Grotesk) headline+wordmark, serif (Source Serif 4) subhead+body, sans (Inter) category/metadata/handle", "Constrain body copy to the measure", "..."]
  dont: ["No hue of any kind", "No icons/illustrations", "No centering", "Never use display face for body/subhead/category", "Never use serif for headline/category/metadata", "Max 2 weights per family", "No shadows/gradients/rounded corners", "..."]
```

The full Swiss / International Typographic Style — three type voices (Space
Grotesk display + Source Serif 4 editorial + Inter interface), named type
roles, 8px spacing grid, per-format margins, body measure, footer wordmark,
and the do/don't checklist. Injected verbatim into the designer and verifier
prompts.

## Token Variable Reference (CSS Variable → YAML Value)

| CSS Variable | Token Path (tokens.yaml) | Example Value |
|---|---|---|
| `var(--color-bg)` | `--color-bg` | `#FFFFFF` (white ground) |
| `var(--color-bg-inverted)` | `--color-bg-inverted` | `#000000` (black ground) |
| `var(--color-text)` | `--color-text` | `#000000` (ink on light ground) |
| `var(--color-text-inverted)` | `--color-text-inverted` | `#FFFFFF` (ink on black ground) |
| `var(--color-text-secondary)` | `--color-text-secondary` | `#6E6E6E` (gray-600 metadata) |
| `var(--color-text-tertiary)` | `--color-text-tertiary` | `#B0B0B0` (gray-300, rare) |
| `var(--color-border)` | `--color-border` | `#D9D9D9` (hairline on white) |
| `var(--color-border-inverted)` | `--color-border-inverted` | `#2A2A2A` (hairline on black) |
| `var(--font-sans)` | `--font-sans` | `Inter, 'Helvetica Neue', Arial, sans-serif` |
| `var(--font-display)` | `--font-display` | `Space Grotesk, Inter, sans-serif` |
| `var(--font-serif)` | `--font-serif` | `Source Serif 4, Georgia, serif` |
| `var(--radius-sm)` | `--radius-sm` | `0px` |
| `var(--radius-md)` | `--radius-md` | `0px` |
| `var(--shadow-md)` | `--shadow-md` | `none` |

Strictly grayscale — no `--color-primary`/`secondary`/`accent`. Three type
voices: `--font-sans` (Inter, category/metadata/handle), `--font-display`
(Space Grotesk, headline + wordmark), `--font-serif` (Source Serif 4,
subhead + body).

## Directory Structure

```
tasbir/
├── PLAN.md                              ← Project plan & phases
├── AGENTS.md                            ← This file
├── DESIGN.md                            ← Architecture decisions
├── docker-compose.yml
├── .env.example
├── docs/                                ← ADRs + glossary
│   ├── glossary.md
│   └── adr/
│       ├── 0001-two-family-typography.md
│       └── ...
│
├── backend/
│   ├── Dockerfile                       ← API/worker image
│   ├── Dockerfile.playwright            ← Slim render service (chromium headless shell)
│   ├── .dockerignore
│   ├── pyproject.toml                   ← pinned Python deps (single source of truth)
│   │
│   ├── config/
│   │   └── prompts/
│   │       ├── strategist.yaml          ← Aura Vance prompt
│   │       ├── planner.yaml             ← Aria Sol prompt
│   │       ├── copywriter.yaml          ← Julian Sterling prompt
│   │       ├── designer.yaml            ← Marcus Chen prompt
│   │       └── verifier.yaml            ← Victoria Thorne prompt
│   │
│   ├── data/
│   │   ├── design_system/
│   │   │   ├── brand.yaml              ← Brand identity + footer + categories
│   │   │   ├── tokens.yaml             ← Design tokens (CSS vars + 3 font voices)
│   │   │   ├── platforms.yaml          ← Platform dimensions
│   │   │   ├── campaigns.yaml          ← Campaign presets (tone, ground, language)
│   │   │   └── design-instruction.yaml ← Swiss style rules (type voices, roles, measure, archetypes)
│   │   │   └── templates/                  ← Human-authored Jinja2 post templates + catalog.yaml
│   │   ├── illustrations/              ← Vendored CC0 hand-drawn kits (open-peeps/, open-doodles/)
│   │   └── output/{task_id}/           ← Generated HTML + PNG files
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      ← FastAPI app entry (create_all on boot, SPA mount)
│   │   ├── config.py                    ← Pydantic Settings (env-based)
│   │   │
│   │   ├── api/
│   │   │   ├── health.py                ← GET /health
│   │   │   ├── generate.py              ← POST /generate (design_system_id, template_id)
│   │   │   ├── tasks.py                 ← GET /tasks/{id}, DELETE, files (persist-until-TTL), archive, rerender
│   │   │   ├── chat.py                  ← GET/POST /tasks/{id}/chat (agent thread, vision turns)
│   │   │   ├── design_systems.py        ← /design-systems CRUD, logo, preview, from-input job
│   │   │   ├── templates.py             ← /templates CRUD, preview, render, from-image job
│   │   │   ├── agent_jobs.py            ← GET /agent-jobs/{id} (template/design-system jobs)
│   │   │   └── uploads.py               ← POST /uploads (validated media)
│   │   │
│   │   ├── agents/
│   │   │   ├── orchestrator/
│   │   │   │   ├── graph.py             ← LangGraph pipeline (3 nodes, parallel branches)
│   │   │   │   ├── state.py             ← GenerationState + Pydantic models
│   │   │   │   └── nodes/
│   │   │   │       ├── strategist.py    ← LLM node (category + ground)
│   │   │   │       ├── copywriter.py    ← LLM node (parallel, length limits)
│   │   │   │       ├── designer.py      ← LLM node (layout archetype, sanitized output)
│   │   │   │       ├── quality_check.py ← Verifier (deterministic + overflow + vision)
│   │   │   │       ├── renderer.py      ← HTML persistence (tokens/fonts/KateX/images/logo)
│   │   │   │       └── template_renderer.py ← fills a DB template (template-first, user override)
│   │   │   └── prompts/
│   │   │       └── registry.py          ← YAML prompt loader
│   │   │
│   │   ├── services/
│   │   │   ├── llm.py                   ← Gemini/OpenRouter client (+ call_llm_for_tools)
│   │   │   ├── vision.py                ← shared Gemini Vision helper (verifier + agents)
│   │   │   ├── tools/                   ← LLM media tools (find_photo, illustrate)
│   │   │   │   ├── photo.py             ← find_photo tool + providers fallback + embed
│   │   │   │   ├── illustrator.py       ← unified illustrate tool + kit composition
│   │   │   │   └── providers/           ← pexels.py / pixabay.py / wikimedia.py
│   │   │   ├── tokens.py                ← Token/brand/campaign/platform YAML loader + semantic vars
│   │   │   ├── design_instruction.py    ← Swiss style loader + font link builder + archetypes
│   │   │   ├── design_systems.py        ← DB design-system CRUD + pipeline payload + preview
│   │   │   ├── templates.py             ← DB template render/select/slotize (YAML catalog = seed)
│   │   │   ├── template_author.py       ← mockup image → validated Jinja2 template (agent)
│   │   │   ├── brand_agent.py           ← form(+images) → full design system + starters (agent)
│   │   │   ├── fonts.py                 ← curated Google Fonts pool loader (fonts.yaml)
│   │   │   ├── seeding.py               ← first-boot seed of `default` DS + 16 templates
│   │   │   ├── uploads.py               ← magic-byte image validation
│   │   │   ├── formats.py               ← Format dimension helper + platform validation
│   │   │   ├── image_loader.py          ← SSRF-guarded download / base64 pass-through
│   │   │   ├── ssrf.py                  ← SSRF guard (private/loopback/metadata block, LAN allow)
│   │   │   ├── sanitizer.py             ← HTML sanitizer (strict / preserve-system modes)
│   │   │   ├── artifacts.py             ← Output path resolution + delivery helpers
│   │   │   ├── dom_extractor.py         ← Playwright DOM extraction + overflow detection
│   │   │   ├── renderer.py              ← Playwright PNG render client
│   │   │   └── render_server.py         ← Playwright HTTP microservice (Docker, key-authed)
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py              ← Base + model imports
│   │   │   ├── task.py                  ← GenerationTask
│   │   │   ├── audit_log.py             ← AuditLog
│   │   │   ├── chat.py                  ← ChatThread + ChatMessage (per task+format agent thread)
│   │   │   ├── design_system.py         ← DesignSystem (brand/tokens/campaigns/DI/logo)
│   │   │   ├── template.py              ← Template (scoped per design system)
│   │   │   └── agent_job.py             ← AgentJob (template/design-system background jobs)
│   │   │
│   │   ├── db/
│   │   │   ├── session.py               ← SQLite async engine
│   │   │   └── repositories/
│   │   │       ├── tasks.py
│   │   │       ├── audit_logs.py
│   │   │       ├── chat.py
│   │   │       ├── design_systems.py
│   │   │       ├── templates.py
│   │   │       └── agent_jobs.py
│   │   │
│   │   ├── tasks/
│   │   │   ├── celery_app.py            ← Celery config (+ hourly beat schedule)
│   │   │   ├── generate.py              ← Celery task (loads config, runs pipeline)
│   │   │   ├── agent_jobs.py            ← template-from-image + design-system-from-input
│   │   │   └── retention.py             ← TTL sweep (expired outputs + task rows)
│   │   │
│   │   └── core/
│   │       ├── dependencies.py          ← FastAPI deps
│   │       ├── security.py              ← API key verification (fails closed)
│   │       ├── ratelimit.py             ← Redis token-bucket rate limiter
│   │       ├── errors.py                ← Error handling
│   │       └── logging.py               ← Logging config
│   │
│   └── tests/
│       ├── test_api/                    ← Route tests (auth, files, rerender, rate limit)
│       ├── test_agents/                 ← Graph & node tests
│       └── test_services/               ← Service tests (SSRF, sanitizer, retention, artifacts)
│
├── frontend/
│   ├── Dockerfile                       ← Node build → static output (staged into volume)
│   ├── components.json                  ← shadcn/ui config (new-york, neutral)
│   ├── package.json / pnpm-lock.yaml / vite.config.ts
│   ├── src/
│   │   ├── main.tsx / App.tsx           ← Router + SWRConfig + ThemeProvider
│   │   ├── lib/
│   │   │   ├── api.ts                   ← Typed API client (API key header, fetch helpers)
│   │   │   ├── theme.tsx                ← Light/dark/system theme provider
│   │   │   └── utils.ts                 ← cn() from shadcn
│   │   ├── hooks/
│   │   │   ├── use-task.ts              ← SWR polling hooks (task + files)
│   │   │   └── use-library.ts           ← design systems / templates / agent jobs
│   │   ├── components/
│   │   │   ├── ui/                      ← shadcn-generated components only
│   │   │   ├── layout/                  ← AppShell (nav), ThemeToggle
│   │   │   ├── tasks/                   ← StatusBadge, template gallery, PreviewFrame, Dropzone, InspectorRail
│   │   │   ├── editor/                  ← HtmlEditor (lazy Monaco), VisualEditor (lazy GrapesJS), AgentChat, QCReport
│   │   │   └── settings/                ← ApiKeyDialog
│   │   └── pages/
│   │       ├── task-list.tsx            ← Task table (lazy, row-click → detail)
│   │       ├── task-detail.tsx          ← Code/Visual edit + live preview + inspector (QC + agent chat) + ZIP
│   │       ├── new-task.tsx             ← /new wizard (design system → content → template → media)
│   │       ├── templates.tsx            ← Template library management (+ from-image job)
│   │       ├── design-systems.tsx       ← Design system editor (+ from-input job)
│   │       ├── agents.tsx               ← Agent configs + pipeline graph
│   │       └── settings.tsx             ← Platforms / curated fonts / runtime knobs
│   └── routes: `/`, `/new`, `/tasks/:taskId`, `/templates`, `/design-systems`,
│              `/agents`, `/settings`
```

## Common Tasks For AI Agents

### Adding a new platform (format)
1. Add it in the Studio **Settings → Platforms** (or `POST /api/platforms`)
   — `id`, name, width × height, family. No YAML edit or restart needed.
2. The pipeline and Studio derive dims + family from the `platforms` table.

### Adding a new campaign preset
1. Edit the design system's campaigns in the Studio (per-design-system, DB)
   — tone, ground (`white` | `black`), and a verbal `language` hint.
2. Reference by name in API: `"campaign": "educational"`

### Adding a new agent
1. Create YAML prompt in `backend/config/prompts/{agent}.yaml`
2. Create Pydantic I/O models in `backend/app/agents/orchestrator/state.py`
3. Create node in `backend/app/agents/orchestrator/nodes/{agent}.py`
4. Register in `backend/app/agents/orchestrator/graph.py`

### Editing agent prompts
Edit them in the Studio **Agents** page (persona, system prompt, model,
temperature, max_tokens) — prompts are DB-backed and apply within ~5s, no
restart needed. `Reset to seed` restores the YAML seed; the YAML files in
`backend/config/prompts/` only seed first boot.

### Adding a new token variable
1. Add `--variable-name: "value"` to `data/design_system/tokens.yaml`
2. Add the semantic role description to `SEMANTIC_VAR_ROLES` in `backend/app/services/tokens.py` (this is what the designer prompt sees)
3. Add default value to `DEFAULT_TOKEN_VALUES` in `backend/app/services/tokens.py`
4. Document the new variable in AGENTS.md Token Variable Reference table

### Changing a typeface / font voice
1. Edit the `--font-*` value in `data/design_system/tokens.yaml`
2. The Google Fonts link, CSS-variable reference, and fallback HTML all derive from it — no code changes
3. Multi-word family names are auto-quoted at injection time (Chromium rejects unquoted names like `Source Serif 4`)
4. Restart the worker to pick up changes

### Adding a layout archetype
1. Add a key + description under `layout_archetypes` in `data/design_system/design-instruction.yaml`
2. The pipeline picks one deterministically per post (seeded by title + format)
3. The verifier audits within any approved archetype — update `verifier.yaml`/design-instruction `do_dont` if the new archetype changes constraints
4. Restart the worker to pick up changes

### Overriding copy fields
1. Set `overrides.headline`, `overrides.subhead`, etc. in the API request
2. Or set `overrides.badge` / `overrides.tagline` / `overrides.category` in `brand.yaml`
3. Copywriter applies copy overrides before calling LLM; category overrides are applied by the strategist

### Modifying design-instruction.yaml (palette, type scale, spacing, do/don't)
1. Edit values in `data/design_system/design-instruction.yaml`
2. No code changes needed — loaded dynamically by the designer and verifier nodes
3. Restart the worker to pick up changes

### Forcing a category label
1. Pass `"category": "PROJECT"` (or any approved label) in POST /generate
2. Or set `overrides.category` in `brand.yaml`
3. The strategist validates against the approved list and falls back to WRITING

### Adding embedded images
1. Include `images` array in POST /generate request
2. Each image: `{url, alt, description, placement}`
3. Placement options: `auto`, `background`, `top-left`, `center`, `bottom-right`

### Auto-media (LLM tools)
Templates and the Designer can pull media automatically via LLM tools — always
**LLM-decided and LLM-driven** (never forced, no deterministic fallback pool):
- **`find_photo(query, orientation?, min_width?)`** — returns a numbered
  **shortlist** of stock-photo candidates (Pexels → Pixabay → Wikimedia
  Commons; unkeyed providers skipped); the LLM then calls **`choose_photo(index)`**
  to pick, or refines its query. Downloads are SSRF-guarded, photos render
  grayscale with an attribution caption, and credits land on the task result
  as `media_credits`. Add a key via `PEXELS_API_KEY` / `PIXABAY_API_KEY`;
  Wikimedia needs none.
- **`illustrate(style: anthropic|open-peeps|open-doodles, theme, ground)`** —
  unified illustration director. `anthropic` is the procedural generator;
  `open-peeps`/`open-doodles` compose vendored CC0 SVGs
  (`backend/data/illustrations/`) recolored to `var(--color-*)`.

Triggers: a template with exactly one empty image slot and no user media runs
a neutral photo director (it may decline); any template with
`{{ illustration | safe }}` runs a neutral illustration director. LLM-designed
posts get both via the media director. The director prompts are neutral ("add
media only if it genuinely strengthens the post"), multi-turn tool use runs via
`call_llm_tool_loop`, and results are cached once per post
(`app/agents/orchestrator/post_cache.py`). A declined/failed media call leaves
the slot empty.

### Adding a template
Templates are DB-backed (v0.5) and scoped to a design system. Prefer the
Studio flow (edit / save-as-template / from-image agent). Programmatically:
1. `POST /templates` with `{name, design_system_id, family, grounds, html}`
   — HTML uses `var(--color-*)` tokens, `data-slot` attributes, and
   `{{ width }}`/`{{ height }}` for the parametric canvas size
2. Optional image slot: `{% if has_image %}<img data-image-key="0">{% endif %}`
3. Optional logo slot: `{% if logo %}<img class="logo" data-logo src="{{ logo }}">{% endif %}`
4. The API validates render + overflow before saving
5. Existing `data/design_system/templates/*.html` + `catalog.yaml` only seed the
   `default` system on first boot

### Creating a template from an image (agent)
1. `POST /templates/from-image` (multipart `file` + `design_system_id`) → `{job_id}`
2. Poll `GET /agent-jobs/{id}` until `completed`; the result has `template_id`
3. The chain: vision (layout spec) → author (Jinja2) → validate (overflow + QC, retry-on-critique)

### Creating a design system with AI
1. `POST /design-systems/from-input` (multipart form + optional `reference_image`/`logo_image`) → `{job_id}`
2. Poll `GET /agent-jobs/{id}` until `completed`; the result has `design_system_id`
3. The chain: brand vision → tokens (from curated `fonts.yaml` pool) → campaigns
   → starter square/landscape templates → persist
4. The `default` design system cannot be deleted; logos are stored base64 in the row

### Testing
```bash
# Backend (pytest)
cd backend && .venv/bin/python -m pytest

# Frontend (typecheck + build)
cd frontend && pnpm run build
```

### Running Tasbir Studio locally
```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && pnpm install && pnpm run dev   # proxies /generate,/tasks,/health → :8000
```
The API requires `x-api-key`; set `API_KEYS=...` in `backend/.env`, then paste
the key into the Studio header dialog (stored in localStorage under `tasbir:apikey:v1`).

### Rebuilding for Docker
```bash
docker compose up -d --build
```
The `frontend` service builds the SPA and stages `dist/` into a shared volume
that the `api` service mounts at `/app/static`. `beat` runs the hourly
`retention.sweep_expired` sweep.

## API Endpoints

### POST /generate
```json
{
  "content": "Full article text...",
  "title": "Article Title",
  "excerpt": "Short summary...",
  "tags": ["ai", "math"],
  "platforms": ["instagram-square", "linkedin-post"],
  "campaign": "default",
  "category": "WRITING",
  "overrides": {
    "headline": "Custom Headline"
  },
  "design_system_id": "default",
  "template_id": "square-editorial-stack",
  "ratio": "square",
  "sequence_audit": false,
  "images": [
    {
      "url": "https://example.com/image.png",
      "alt": "Description",
      "description": "Place this near the headline",
      "placement": "auto"
    }
  ]
}
```
Response: `{"task_id": "uuid", "status": "pending"}`

Requires `x-api-key` header. Rate-limited per key (default 30 req/min).
`design_system_id` selects the brand system (default `default`); `template_id`
locks a template for matching families (auto-fallback otherwise). Images may
also be pre-embedded: `{data, mime, alt, description, placement}` (uploaded via
`POST /uploads`).

**Planner & carousels**: `platforms: ["auto"]` lets the planner choose the
platform set and structure. For carousels, `slides` (2-10) and `ratio`
(`square` | `portrait` | `auto`) set the frame count/aspect; `ratio: "auto"`
or an unpinned `slides` delegates to the planner. `sequence_audit: true`
runs an opt-in vision audit of the whole slide set (one call).

### Design systems API
- `GET /design-systems` · `POST /design-systems` · `GET/PUT/DELETE /design-systems/{id}`
- `POST/DELETE /design-systems/{id}/logo` (multipart, raster only)
- `POST /design-systems/{id}/preview` → `{html}` (live sample render)
- `POST /design-systems/from-input` (multipart form + optional reference/logo images) → `{job_id}`

### Templates API
- `GET /templates?design_system_id=&family=` · `POST /templates` · `GET/PUT/DELETE /templates/{id}`
- `POST /templates/{id}/render` (validate) · `POST /templates/{id}/preview` → `{html}`
- `POST /templates/from-image` (multipart `file` + `design_system_id`) → `{job_id}`

### Agent jobs + uploads
- `GET /agent-jobs/{id}` — poll template/design-system creation jobs
- `POST /uploads` — validated image upload → `{mime, size, data(base64)}`

### GET /tasks/{id}
Response:
```json
{
  "id": "uuid",
  "status": "running|completed|failed",
  "source_data": { ... },
  "result": {
    "output_paths": {
      "instagram-square": {
        "html": "data/output/task-id/instagram-square.html",
        "png": "data/output/task-id/instagram-square.png"
      },
      "linkedin-post": {
        "html": "data/output/task-id/linkedin-post.html",
        "png": "data/output/task-id/linkedin-post.png"
      }
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

### GET /tasks/{id}/files
Lists remaining artifacts: `[{"format", "ext", "size", "filename"}, ...]`.

### GET /tasks/{id}/files/archive
Streams every remaining artifact (HTML + PNG) for the task as one ZIP
(`{task_id}.zip`). Non-consuming — files stay until the TTL sweep.

### GET /tasks/{id}/files/{filename}
Streams an artifact. Files persist until the TTL sweep; downloads are
repeatable. `?consume=true` deletes the file after delivery (one-time download).

### GET /tasks/{id}/chat?format={fmt}
Returns (lazily creating) the agent-chat thread for a (task, format):
`{"thread_id", "format", "messages": [{"id", "role", "content", "html", "created_at"}]}`.

### POST /tasks/{id}/chat
```json
{ "format": "instagram-square", "message": "Tighten the headline",
  "html": "<optional current editor HTML>" }
```
Runs one turn with the design assistant (Marcus Chen — collaborative mode,
vision-capable: it sees the current render when available). If a change is
requested it returns a full replacement document. Response:
`{"reply", "html" (nullable), "qc": {"ok", "issues"} | null, "thread_id"}`.
Thread + messages persist in the DB (`chat_threads`/`chat_messages`); the
frontend offers `html` for review before re-rendering (review-then-render).

### POST /tasks/{id}/formats/{fmt}/rerender
```json
{ "html": "<!DOCTYPE html>…" }
```
Re-injects tokens/fonts/KaTeX/images, renders PNG, runs deterministic + overflow
checks. `?audit=true` also runs the vision audit (opt-in to save quota). Skips
the designer LLM. Response: `{"format", "pass", "quality": {"score", "issues", "critique"}, "png_b64"}`.

### POST /tasks/{id}/formats/{fmt}/template
```json
{ "name": "bold-index", "mode": "new" }   // mode: new | update
```
Promotes the current render (or your edit) into the template library. `mode=update`
replaces the source template the post came from; `mode=new` creates one. Validated
(render + overflow) before saving. Response: `{"template_id", "mode", "file"}`.

### GET /health
Response: `{"status": "ok"}`

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `OPENROUTER_API_KEY` | No | — | Fallback LLM provider |
| `PEXELS_API_KEY` | No | — | Stock-photo search (media tools) |
| `PIXABAY_API_KEY` | No | — | Stock-photo search (media tools); Wikimedia Commons needs none |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Celery broker |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///data/tasbir.db` | SQLite for task tracking |
| `API_KEYS` | Yes* | — | Comma-separated API keys (auth fails closed if empty) |
| `RATE_LIMIT_PER_MIN` | No | `30` | Per-key requests/minute |
| `RENDER_SERVICE_KEY` | No* | — | Shared secret with the internal Playwright service (Docker) |
| `IMAGE_ALLOW_HOSTS` | No | — | Extra trusted hosts for image fetch (SSRF opt-in) |
| `IMAGE_MAX_BYTES` | No | `10485760` | Max bytes per downloaded image |
| `IMAGE_MAX_REDIRECTS` | No | `2` | Max image-fetch redirects |
| `OUTPUT_TTL_HOURS` | No | `24` | Artifact + task retention window (hours) |
| `SKIP_VERIFY` | No | `false` | Dev only: auto-pass the vision verifier |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Allowed origins |
| `LOG_LEVEL` | No | `info` | Logging level |

\* Required for Docker deployments (`API_KEYS`, `RENDER_SERVICE_KEY`).
