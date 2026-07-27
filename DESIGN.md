# Tasbir v2 — Architecture & Design

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE                               │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  Caddy   │  │  FastAPI  │  │  Celery  │  │      SvelteKit       │ │
│  │  Proxy   │──│  (API)   │──│  Worker  │  │       (UI)           │ │
│  │  :443    │  │  :8000   │  │          │  │       :5173          │ │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └──────────────────────┘ │
│                     │              │                                  │
│                     │     ┌────────┴────────┐                        │
│                     │     │   PostgreSQL    │                        │
│                     │     │    :5432        │                        │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │     Redis       │                        │
│                     │     │    :6379        │                        │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │     MinIO       │                        │
│                     │     │    :9000        │                        │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │   Playwright    │                        │
│                     │     │    :4000        │                        │
│                     │     └─────────────────┘                        │
│                     │     ┌────────┴────────┐                        │
│                     │     │    Penpot       │                        │
│                     │     │    :9001        │                        │
│                     │     └─────────────────┘                        │
│                     │                                                │
│  ┌──────────────────┴──────────────────────────────────────┐         │
│  │                    External Services                     │         │
│  │  Google AI Studio  │  Unsplash API  │  Ghost CMS        │         │
│  │  (free Gemini)     │  (free photos) │  (webhook source) │         │
│  └──────────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow & Serial Agent Architecture

The pipeline runs **serially** (one node at a time) to stay within Gemini free tier TPM limits. Within each node, multiple formats process in parallel via `asyncio.gather()` with semaphores.

### Generation Pipeline Flow

```
Ghost Webhook / UI Request
         │
         ▼
  ┌──────────────┐
  │  FastAPI      │  Creates Celery task, returns { task_id }
  │  POST /generate │
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │  Celery Worker │  Pre-loads design tokens from DB by brand name
  │  generate_task │  Injects tokens into state before pipeline runs
  └──────┬───────┘
         │
    ┌────┴────┐
    │ LangGraph │
    │ Pipeline  │  SERIAL graph edges
    └────┬────┘
         │
    ┌────┴────────┐
    │Strategist   │  Aura Vance — content analysis
    │Node 1       │  1 LLM call (serial)
    └────┬────────┘
         │
    ┌────┴────────┐
    │Copywriter   │  Julian Sterling — copy per format
    │Node 2       │  X formats in parallel via Semaphore(3)
    └────┬────────┘
         │
    ┌────┴────────┐
    │Visual Dir.  │  Elena Rostova — backgrounds per format
    │Node 3       │  X formats in parallel via Semaphore(3)
    └────┬────────┘
         │
    ┌────┴────────┐
    │Designer     │  Marcus Chen — HTML per format
    │Node 4       │  X formats in parallel via Semaphore(2)
    │             │  Calls build_config_html(tokens) which:
    │             │    1. Runs tailwindcss CLI to compile @theme → CSS
    │             │    2. Inlines compiled Tailwind CSS in <style>
    │             │    3. Adds Google Fonts link
    └────┬────────┘
         │
    ┌────┴────────┐
    │Quality Check│  Victoria Thorne — LLM audit + programmatic fallback
    │Node 5       │  If score < 50 and refinements < 2 → back to Designer
    └────┬────────┘
         │
    ┌────┴────────┐
    │ Playwright  │  HTML → PNG via headless Chromium
    │ Renderer    │  Parallel per format via Semaphore(2)
    └────┬────────┘
         │
         ▼
   MinIO Storage
```

## Design Token Flow

```
User creates brand + tokens via API
         │
         ▼
   DesignToken table (PostgreSQL)
         │
         ▼
   Celery generate_task loads tokens by brand name
         │
         ▼
   Pipeline state → Designer node
         │
         ▼
   _inject_theme(html, tokens)
    ├─ build_config_html(tokens)
    │   ├─ _generate_theme_css(merged)
    │   │   Maps known DTCG paths to @theme CSS variables:
    │   │   - brand.primary.main → --color-primary
    │   │   - neutral.bg → --color-bg
    │   │   - semantic.text.primary → --color-text
    │   │   - typography.fontFamily.sans → --font-sans
    │   │   - spacing.4 → --spacing-4
    │   │   - etc.
    │   ├─ _compile_tailwind(theme_css)
    │   │   Runs tailwindcss CLI (standalone binary)
    │   │   Generates full utility CSS (bg-*, text-*, font-*, p-*, etc.)
    │   └─ Returns <style> block with compiled CSS
    ├─ Google Fonts <link>
    └─ Fallback :root CSS variables
```

## Token Generator Agent (Dr. Soren Lindqvist)

The token generator is a standalone LangGraph agent with 11 tools:
- `check_contrast_tool` — WCAG AA/AAA contrast validation for any color pair
- `generate_colors_tool` — Accessible color palette with brand, neutral, semantic colors
- `generate_typography_tool` — Font families, sizes, weights, line heights
- `generate_spacing_tool` — Spacing scale (rem/px)
- `generate_borders_tool` — Border radius + box shadows
- `search_templates`, `search_unsplash`, `generate_background_tool`, `fetch_design_tokens`, `render_preview`, `svg_illustration`

The agent calls tools to generate each token category, validates contrast, and assembles the final DTCG JSON.

## Real-Time Progress

Replaced SSE polling with Socket.IO (python-socketio v5.16):
- Celery worker emits progress via `RedisManager(write_only=True)` 
- FastAPI Socket.IO server delivers to browser clients
- Auto-reconnection, per-task rooms, cross-tab sync via BroadcastChannel

## Core Design & Technical Constraints

1. **Pure Standalone Visual Graphic Canvas**: No nav, buttons, forms, or interactive elements.
2. **Strict No-Emoji Rule**: Enforced by system prompts + `remove_emojis()` in `cleanup.py`.
3. **Dynamic Database Format Lookup**: Formats loaded from `Format` table.
4. **Intra-Node Format Concurrency**: `asyncio.gather()` with semaphores inside agent nodes.
5. **Server-Side Tailwind CSS Compilation**: Uses `tailwindcss` standalone CLI v4 to compile @theme variables into full utility CSS. No CDN dependency, no JavaScript execution in browser.

## Agent Personas & Prompt Registry

All agent system prompts are versioned in PostgreSQL (`prompt_registry` & `prompt_versions`):

| Agent Name | Studio Role | Primary Responsibilities |
|---|---|---|
| `strategist` | Aura Vance | Strategic brief, target audience, brand tone, visual narrative pillars. |
| `copywriter` | Julian Sterling | Visual copy layout structuring (Headline, Hook, Highlights, Badge, CTA). |
| `visual_director` | Elena Rostova | Art direction, CSS mesh gradients, glassmorphism, Unsplash stock photos. |
| `designer` | Marcus Chen | HTML+Tailwind visual graphic canvas creation, typography hierarchy, zero overflow. |
| `quality_check` | Victoria Thorne | Audit score (0-100), placeholder hygiene, layout overflow detection. |
| `token_generator` | Dr. Soren Lindqvist | W3C DTCG design token generation. |

## Background Generation (Zero Cost)

Images are generated with zero API costs:

### Tier 1: CSS Gradients & Glassmorphism
Linear, radial, and mesh gradients with `backdrop-filter: blur()`.

### Tier 2: SVG Patterns
Code-generated dot grids, subtle wave lines, and geometric motifs.

### Tier 3: Unsplash Stock Photography
Free stock photography search via `search_unsplash` tool.

## API & UI Prompt Management

```
GET  /prompts              → List active prompts
GET  /prompts/{name}       → Fetch prompt definition
PUT  /prompts/{name}       → Update prompt & create version history record
POST /prompts/{name}/restore → Restore previous version
```

In the UI (**Configure → Prompts** tab), users can visually edit system prompts, modify temperature and token limits, and save changes directly to the database.
