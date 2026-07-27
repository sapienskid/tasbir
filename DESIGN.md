# Tasbir v3 — Architecture & Design

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE                               │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  Caddy   │  │  FastAPI  │  │  Celery  │  │      Penpot         │ │
│  │  Proxy   │──│  (API)   │──│  Worker  │  │      :9002          │ │
│  │  :443    │  │  :8000   │  │          │  │  (design tool)       │ │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └──────────────────────┘ │
│                     │              │                                  │
│                     │     ┌────────┴────────┐                        │
│                     │     │     Redis       │                        │
│                     │     │    :6379        │                        │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │  PostgreSQL      │                        │
│                     │     │  :5432           │  (Penpot only)         │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │   Playwright    │                        │
│                     │     │    :4000        │  (DOM extraction)      │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │  SQLite (file)  │  (task tracking)       │
│                     │     └─────────────────┘                        │
│                     │                                                │
│  ┌──────────────────┴──────────────────────────────────────┐         │
│  │                    External Services                     │         │
│  │  Google AI Studio  │  n8n Workflow  │  Ghost CMS        │         │
│  │  (free Gemini)     │  (triggers)    │  (content source) │         │
│  └──────────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow & Multi-Agent Architecture

The pipeline uses LangGraph with typed state. Each agent is a dedicated node.
Formats are processed in parallel via Send fan-out.

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
   │  Celery Worker│  Loads Design System .penpot file
   │  generate_task│  Runs full LangGraph pipeline
   └──────┬───────┘
          │
     ┌────┴────┐
     │ LangGraph │
     │ Pipeline  │
     └────┬────┘
          │
     ┌────┴────────┐
     │Strategist   │  Aura Vance — content analysis
     │Node 1       │  1 LLM call (serial)
     └────┬────────┘
          │
     ┌────┴────────┐
     │Copywriter   │  Julian Sterling — copy per format
     │Node 2       │  X formats in parallel via Send fan-out
     └────┬────────┘
          │
     ┌────┴────────┐
     │Designer     │  Marcus Chen — HTML per format
     │Node 3       │  X formats in parallel via Send fan-out
     │             │  Template path: Penpot board fills slots
     │             │  Custom path: writes HTML from scratch
     │             │  CSS variables only: var(--color-*)
     └────┬────────┘
          │
     ┌────┴────────┐
     │HTML→Penpot  │  PROGRAMMATIC ONLY — no LLM
     │Node 4       │  1. Playwright → DOM tree
     │             │  2. Map DOM → .penpot shapes
     │             │  3. Resolve CSS vars → Penpot tokens
     │             │  4. Math: KaTeX→SVG, Diagrams: Mermaid→SVG
     │             │  5. Build valid .penpot ZIP
     └────┬────────┘
          │
     ┌────┴────────┐
     │Verifier     │  Victoria Thorne — multimodal QC
     │Node 5       │  Input: rendered PNG + design system + target platform
     │             │  Output: {pass, score, issues, critique}
     │             │
     │             ├── [pass] → END (success)
     │             └── [fail + retry<2] → Designer with critique context
     └─────────────┘
```

## Design System & Template Architecture

### Single Source of Truth: `data/design_system/Tasbir Design System.penpot`

This is a `.penpot` file (ZIP archive) containing:
- `tokens.json` — complete DTCG design tokens (colors, fonts, spacing, shadows, etc.)
- `pages/` — one page per platform/format
  - Each page contains template boards (pre-designed layouts)
  - Template boards have text layers named as slots: `{{headline}}`, `{{body}}`, `{{tagline}}`, `{{badge}}`
  - Boards use design tokens for colors and typography

### How Templates Work

1. **At pipeline start**: Read design system file → extract tokens + template boards
2. **Template Selector** (in Designer node): LLM picks the best template board for each platform
3. **Template Filler** (in Designer node): Fills named text layers with copywriter output
4. **If no template fits**: Designer writes custom HTML from scratch with CSS variables

### How Tokens Work

1. All design tokens live in `tokens.json` inside the design system `.penpot` file
2. The Designer writes CSS variables: `var(--color-bg)`, `var(--color-text)`, etc.
3. During HTML→Penpot conversion, CSS variables are resolved to actual hex values
4. The LLM NEVER sees actual brand colors or token values — it only uses variable names

### User Workflow

1. Designer creates/modifies templates in Penpot → exports as .penpot → places in `data/design_system/`
2. n8n triggers pipeline → generates designs as new .penpot files
3. User opens generated .penpot in Penpot → reviews, edits, polishes
4. Good designs → user copies board to Design System file → becomes new template
5. Token changes in Design System file → cascade to all future generations

## Storage Architecture

### SQLite (for runtime state)

```
generation_tasks: id(TEXT), status(TEXT), source_data(TEXT JSON),
                  result(TEXT JSON), error(TEXT), created_at, updated_at
audit_logs:       id(INT), task_id(TEXT FK), agent_name(TEXT),
                  decision(TEXT JSON), critique(TEXT), created_at
```

### .penpot Files (for design data)

```
data/
├── design_system/
│   └── Tasbir Design System.penpot    ← tokens + templates (single source of truth)
└── output/{task_id}/
    └── {task_id}.penpot               ← generated design (per generation task)
        ├── instagram-square board     ← one board per requested platform
        ├── linkedin-post board
        └── twitter-card board
```

## HTML → Penpot Converter

### Why This Approach

- Playwright's browser engine computes layout (flexbox, grid, font metrics) perfectly
- We extract the computed DOM tree → map to .penpot shape types
- Full HTML support: any HTML/CSS the Designer writes gets correctly converted
- Math/diagrams handled as SVG: KaTeX/Mermaid → SVG → Penpot `svg-raw` shape

### Conversion Pipeline

```
Designer HTML → Playwright (headless) → Computed DOM tree
                                              │
                                    Extract: type, position, size,
                                    fills, borders, fonts, text runs
                                              │
                                    Map element types → Penpot shapes:
                                      div/body → frame
                                      h1-h6/p/span → text
                                      img → image
                                      .math → KaTeX SVG → svg-raw
                                      .diagram → Mermaid SVG → svg-raw
                                              │
                                    Resolve CSS variables:
                                      var(--color-*) → actual token values
                                              │
                                    Build .penpot ZIP:
                                      manifest.json + file metadata +
                                      page + shapes + tokens.json +
                                      embedded SVGs in objects/
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
| `strategist` | Aura Vance | Strategic brief, target audience, brand tone, visual narrative pillars. |
| `copywriter` | Julian Sterling | Visual copy (Headline, Subhead, Body, Tagline, Badge). |
| `designer` | Marcus Chen | HTML poster with CSS variables, typography hierarchy, zero overflow. |
| `verifier` | Victoria Thorne | Multimodal audit on rendered PNG, scores 0-100, actionable critique. |

## Core Design & Technical Constraints

1. **Penpot-Native Output**: Pipeline outputs `.penpot` files, not PNGs. User exports from Penpot if needed.
2. **Strict No-Emoji Rule**: Enforced via system prompts.
3. **CSS Variables Only**: Designer writes `var(--color-*)` — never raw hex colors.
4. **Design Tokens Not in Prompts**: LLM never sees actual token values.
5. **Full HTML Support**: Playwright DOM extraction handles any HTML/CSS the Designer writes.
6. **Intra-Node Format Concurrency**: `asyncio.gather()` with semaphores for parallel platform processing.
7. **Typed Agent I/O**: Every agent uses Pydantic models, not markdown parsing.
