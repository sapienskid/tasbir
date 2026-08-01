# Tasbir v3 — Architecture & Design

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE                               │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                           │
│  │  FastAPI  │  │  Celery  │  │ Playwright│                          │
│  │  (API)   │──│  Worker  │──│  :4000   │                           │
│  │  :8000   │  │          │  │ (render)  │                           │
│  └────┬─────┘  └────┬─────┘  └──────────┘                           │
│       │              │                                                │
│       │     ┌────────┴────────┐                                       │
│       │     │     Redis       │                                       │
│       │     │    :6379        │                                       │
│       │     └─────────────────┘                                       │
│       │     ┌────────┴────────┐                                       │
│       │     │  SQLite (file)  │  (task tracking)                     │
│       │     └─────────────────┘                                       │
│       │     ┌────────┴────────┐                                       │
│       │     │  data/output/   │  (HTML + PNG files)                   │
│       │     └─────────────────┘                                       │
│       │                                                               │
│  ┌─────┴────────────────────────────────────────────────────┐        │
│  │                    External Services                      │        │
│  │  Google AI Studio  │  n8n Workflow  │  Ghost CMS          │        │
│  │  (free Gemini)     │  (triggers)    │  (content source)   │        │
│  └───────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow & Multi-Agent Architecture

The pipeline uses LangGraph with typed state. Each agent is a dedicated node.
Formats are processed in parallel via asyncio.gather with isolated per-format branches (no reducer races).

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
   │  Celery Worker│  Loads YAML design system (brand, tokens,
   │  generate_task│  platforms, campaigns), downloads images,
   │               │  runs full LangGraph pipeline
   └──────┬───────┘
          │
     ┌────┴────┐
     │ LangGraph│
     │ Pipeline │
     └────┬────┘
          │
     ┌────┴────────┐
     │Strategist   │  Aura Vance — content analysis
     │Node 1       │  1 LLM call (serial)
     │             │  Brand + campaign context provided
     └────┬────────┘
          │
     ┌────┴────────┐
     │Copywriter   │  Julian Sterling — copy per format
     │Node 2       │  X formats in parallel via gather+Semaphore
     │             │  Overrides applied before LLM call
     └────┬────────┘
          │
     ┌────┴────────┐
     │Designer     │  Marcus Chen — HTML per format
     │Node 3       │  X formats in parallel via gather (isolated branches)
     │             │  Input: copy + brand + campaign + images
     │             │  CSS variables only: var(--color-*)
     │             │  No brand hex values in prompt
     │             │  Verifier critique included on retry
     └────┬────────┘
          │
     ┌────┴────────┐
     │Verifier     │  Victoria Thorne — render + multimodal QC
     │Node 4       │  1. Inject design tokens as CSS :root
     │             │  2. Inject KaTeX CDN if math detected
     │             │  3. Embed base64 images
     │             │  4. Save HTML to data/output/{task_id}/
     │             │  5. Playwright renders HTML → PNG
     │             │  6. Gemini Vision audits rendered PNG
     │             │  Output: {pass, score, issues, critique}
     │             │
     │             ├── [pass] → END (success)
     │             └── [fail + retry<2] → Designer with critique context
     └─────────────┘
```

## YAML Design System

### Configuration Files in `data/design_system/`

The design system is split into four YAML files, each serving a specific purpose:

| File | Purpose | Loaded By |
|------|---------|-----------|
| `brand.yaml` | Brand identity (name, tagline, mission, story, social links, overrides) | Celery task → all agents |
| `tokens.yaml` | CSS variable → value mappings (colors, fonts, spacing, shadows) | Celery task → Verifier/Designer |
| `platforms.yaml` | Platform dimensions `[width, height]` in pixels | `get_format_info()` |
| `campaigns.yaml` | Visual presets (tone, style, background, illustrations) | Celery task → Strategist/Designer |

### Why YAML

- **Human-readable**: Edit with any text editor, no design tool needed
- **Version-control friendly**: Plain text, git-diffable
- **No external dependencies**: No database, no file format parser beyond PyYAML
- **Fast loading**: YAML is millisecond-fast to parse
- **Composable**: Separate files for brand, tokens, platforms, campaigns — each independently editable

### How Tokens Work

1. All design tokens live in `tokens.yaml` as CSS variable → value mappings
2. The Designer writes CSS variables: `var(--color-bg)`, `var(--color-text)`, etc.
3. The LLM is told what CSS variable names exist (list in system prompt) but NEVER sees actual color values
4. After the Designer outputs HTML, the Verifier injects the actual token values as a `<style>:root { ... }</style>` block
5. The LLM never sees brand colors — only variable names

### How Brand Context Flows

1. `brand.yaml` is loaded at pipeline start
2. Brand name/tagline passed to Strategist for tone alignment
3. Brand name/tagline passed to Copywriter for voice consistency
4. Brand name passed to Designer for visual alignment
5. Overrides (badge, tagline) from `brand.yaml` applied before Copywriter LLM call

### How Campaigns Work

1. API request includes `campaign: "educational"` (string key)
2. Celery task loads the corresponding preset from `campaigns.yaml`
3. Campaign defines: tone, ground (white|black), and verbal language
4. Tone → Strategist, Copywriter, Designer
5. Visual style, background, illustrations → Designer (HTML layout)
6. Campaign presets can be extended by editing `campaigns.yaml` — no code changes needed

### How Images Work

1. API request includes `images: [{url, alt, description, placement}]`
2. Celery task downloads images via HTTP and encodes as base64
3. Images are stored in pipeline state
4. Designer receives image descriptions (alt text, placement) for layout
5. Verifier injects base64 `<img>` tags before rendering

### How KaTeX Works

1. Designer may include `<span class="math">\sum_{i=1}^n i</span>` in HTML
2. The `inject_katex_into_html()` function detects these spans
3. KaTeX CSS + JS + auto-render scripts are injected into `<head>`
4. Playwright renders the page — KaTeX converts LaTeX to SVG at render time
5. No separate SVG generation step needed

### How Mermaid Works

1. Designer may include `<div class="diagram">graph TD...</div>` in HTML
2. Playwright renderer detects `data-mermaid-ready` sentinel
3. Waits for Mermaid to finish rendering before screenshot
4. Mermaid CDN is expected to be included by the Designer in HTML

## Storage Architecture

### SQLite (for runtime state)

```
generation_tasks: id(TEXT), status(TEXT), source_data(TEXT JSON),
                  result(TEXT JSON), error(TEXT), created_at, updated_at
audit_logs:       id(INT), task_id(TEXT FK), agent_name(TEXT),
                  decision(TEXT JSON), critique(TEXT), created_at
```

### File Output (for design data)

```
data/
├── design_system/
│   ├── brand.yaml                ← Brand identity
│   ├── tokens.yaml               ← Design tokens
│   ├── platforms.yaml            ← Platform dimensions
│   └── campaigns.yaml            ← Campaign presets
└── output/{task_id}/
    ├── instagram-square.html     ← Generated HTML (open in browser)
    ├── instagram-square.png      ← Rendered PNG (share ready)
    ├── linkedin-post.html
    └── linkedin-post.png
```

## HTML Render & Verification Pipeline

### Why This Approach

- Playwright's browser engine renders CSS perfectly (flexbox, grid, fonts)
- HTML is the most portable format — open in any browser
- PNG is universal for sharing (social media, messaging)
- Gemini Vision provides automated visual quality assurance
- No proprietary file format dependency

### Render Pipeline

```
Designer HTML
     │
     ▼
[Verifier] injects:
  1. CSS :root variables from tokens.yaml
  2. KaTeX CDN if <span class="math"> detected
  3. Base64 <img> tags for embedded images
     │
     ▼
Save HTML → data/output/{task_id}/{fmt_id}.html
     │
     ▼
Playwright renders HTML → PNG screenshot
     │
     ▼
Gemini Vision audits PNG against design system
     │
     ▼
{pass: true/false, score: 0-100, issues: [...], critique: "..."}
```

## Agent Personas & Prompt Registry

All agent system prompts are stored in YAML files:

```
backend/config/prompts/
├── strategist.yaml
├── copywriter.yaml
├── designer.yaml
└── verifier.yaml
```

| Agent Name | Studio Role | Primary Responsibilities |
|---|---|---|
| `strategist` | Aura Vance | Strategic brief, target audience, brand tone, visual narrative, platform notes. |
| `copywriter` | Julian Sterling | Per-platform copy (Headline, Subhead, Body, Tagline, Badge). Respects overrides. |
| `designer` | Marcus Chen | HTML with CSS variables, typography hierarchy, image placement, zero overflow. |
| `verifier` | Victoria Thorne | Inject tokens/KateX/images, render to PNG, multimodal audit via Gemini Vision, score 0-100. |

## Core Design & Technical Constraints

1. **HTML + PNG Output**: Pipeline outputs `.html` + `.png` files. Open HTML in any browser, share PNG anywhere.
2. **Strict No-Emoji Rule**: Enforced via system prompts.
3. **CSS Variables Only**: Designer writes `var(--color-*)` — never raw hex colors.
4. **Design Tokens Not in Prompts**: LLM never sees actual token values — only variable names.
5. **YAML Configuration**: All brand, token, platform, and campaign data in `data/design_system/*.yaml`.
6. **Intra-Node Format Concurrency**: `asyncio.gather()` with semaphores for parallel platform processing.
7. **Typed Agent I/O**: Every agent uses Pydantic models, not markdown parsing.
8. **Brand Context Everywhere**: Brand name/tagline/mission flows to all agents for consistent voice.
9. **Automatic KaTeX Injection**: Math spans auto-detect and inject KaTeX CDN — no manual setup.
10. **Image Embedding**: Images downloaded and base64-embedded into HTML at pipeline runtime.
