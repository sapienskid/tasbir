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

The design system is split into five YAML files, each serving a specific purpose:

| File | Purpose | Loaded By |
|------|---------|-----------|
| `brand.yaml` | Brand identity (name, tagline, mission, story, social, footer, categories, overrides) | Celery task → all agents |
| `tokens.yaml` | CSS variable → value mappings (grayscale palette, 3 font voices) | Celery task → Verifier/Designer |
| `platforms.yaml` | Platform dimensions `[width, height]` in pixels | `get_format_info()` |
| `campaigns.yaml` | Campaign presets (tone, ground, language) | Celery task → Strategist/Designer |
| `design-instruction.yaml` | Swiss typographic style (type voices, roles, measure, layout archetypes) | Designer + Verifier nodes |

### Why YAML

- **Human-readable**: Edit with any text editor, no design tool needed
- **Version-control friendly**: Plain text, git-diffable
- **No external dependencies**: No database, no file format parser beyond PyYAML
- **Fast loading**: YAML is millisecond-fast to parse
- **Composable**: Separate files for brand, tokens, platforms, campaigns — each independently editable

### How Tokens & Fonts Work

1. All design tokens live in `tokens.yaml` as CSS variable → value mappings
2. The Designer writes CSS variables: `var(--color-bg)`, `var(--color-text)`, etc.
3. The LLM is told what CSS variable names exist (with semantic role descriptions) but NEVER sees actual color values
4. After the Designer outputs HTML, the system injects the actual token values as a `<style>:root { ... }</style>` block
5. Multi-word font families (e.g. `Source Serif 4`) are **quoted automatically** in the injected `:root` — unquoted names silently fall back to Times New Roman in Chromium
6. The Google Fonts `<link>` is generated from the token families + type-scale weights and injected **deterministically** — it never depends on the LLM
7. The render service waits for `document.fonts.ready` before screenshotting so webfonts always render

### How Brand Context Flows

1. `brand.yaml` is loaded at pipeline start
2. Brand name/tagline passed to Strategist for tone alignment
3. Brand name/tagline passed to Copywriter for voice consistency
4. Brand name passed to Designer for visual alignment
5. Overrides (badge, tagline, category) from `brand.yaml` applied before the relevant LLM call

### How Campaigns Work

1. API request includes `campaign: "educational"` (string key)
2. Celery task loads the corresponding preset from `campaigns.yaml`
3. Campaign defines: tone, ground (white|black), and verbal language
4. Tone + language → Strategist, Copywriter, Designer; ground → resolved post background
5. Ground priority: campaign → category (`brand.yaml` `categories[].ground`) → white
6. Campaign presets can be extended by editing `campaigns.yaml` — no code changes needed

### How Typography Works

Three config-driven voices (from `design-instruction.yaml` `type_voice` + `type_scale.roles`):

- **Display** — Space Grotesk (`var(--font-display)`): headline + footer wordmark only
- **Serif** — Source Serif 4 (`var(--font-serif)`): subhead + body copy (editorial measure ~600px)
- **Sans** — Inter (`var(--font-sans)`): category label, metadata, handle

Swapping a face or weight is a YAML-only change — the Google Fonts link, the
CSS-variable reference, and both prompts derive from the same config.

### How Layout Archetypes Work

`design-instruction.yaml` `layout_archetypes` defines approved compositions
(`editorial-stack`, `split-editorial`, `quiet-minimal`). The pipeline picks one
**deterministically per post** (seeded by title + format), so designs vary
across runs while staying on-brand. The verifier audits within any approved
archetype rather than demanding one fixed layout.

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
└── output/{task_id}/             ← EPHEMERAL — persisted until the TTL sweep
    ├── instagram-square.html     ← Generated HTML (open in browser)
    ├── instagram-square.png      ← Rendered PNG (share ready)
    ├── linkedin-post.html
    └── linkedin-post.png
```

Artifacts are delivered once over HTTP (`GET /tasks/{id}/files/{filename}`
streams then deletes) and a hourly Celery beat task sweeps everything older
than `OUTPUT_TTL_HOURS` (default 24h), bounding disk and DB growth. See
ADR-0007.

## HTML Render & Verification Pipeline

### Why This Approach

- Playwright's browser engine renders CSS perfectly (flexbox, grid, fonts)
- HTML is the most portable format — open in any browser
- PNG is universal for sharing (social media, messaging)
- Gemini Vision provides automated visual quality assurance
- No proprietary file format dependency

### Render Pipeline

```
Designer HTML (per format)
     │
     ▼
[Renderer / Verifier] injects deterministically:
  1. CSS :root variables from tokens.yaml (font families auto-quoted)
  2. Google Fonts <link> (derived from type-scale families + weights)
  3. KaTeX CDN if <span class="math"> detected
  4. Base64 <img> tags for embedded images
     │
     ▼
Save HTML → data/output/{task_id}/{fmt_id}.html
     │
     ▼
Playwright renders HTML → PNG (waits for document.fonts.ready)
     │
     ▼
Deterministic checks (no LLM): emoji, raw hex, footer, category,
display face, canvas size, DOM-based overflow → hard fail + retry
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
| `strategist` | Aura Vance | Strategic brief, target audience, brand tone, category, ground, platform notes. |
| `copywriter` | Julian Sterling | Per-platform copy (Headline, Subhead, Body, Tagline). Respects overrides + length limits matched to the design measure. |
| `designer` | Marcus Chen | HTML with CSS variables, three-voice typography, layout archetype, image placement, zero overflow. |
| `renderer` | — | Deterministic injection: tokens, fonts link, KaTeX, images. Saves HTML. |
| `verifier` | Victoria Thorne | Deterministic checks (emoji/hex/footer/category/display-face/canvas/overflow) + PNG render + multimodal audit, score 0-100. |

## Core Design & Technical Constraints

1. **HTML + PNG Output**: Pipeline outputs `.html` + `.png` files. Open HTML in any browser, share PNG anywhere.
2. **Strict No-Emoji Rule**: Enforced via system prompts + deterministic emoji scan.
3. **CSS Variables Only**: Designer writes `var(--color-*)` — never raw hex colors. Hex in the designer's own HTML is a deterministic violation.
4. **Design Tokens Not in Prompts**: LLM never sees actual token values — only variable names + semantic roles.
5. **YAML Configuration**: All brand, token, platform, campaign, and typography data in `data/design_system/*.yaml`. Fonts links and the CSS-variable reference are generated from YAML — no hardcoded design values in code.
6. **Intra-Node Format Concurrency**: `asyncio.gather()` with isolated per-format branches (no reducer races).
7. **Typed Agent I/O**: Every agent uses Pydantic models, not markdown parsing.
8. **Brand Context Everywhere**: Brand name/tagline/mission flows to all agents for consistent voice.
9. **Automatic KaTeX Injection**: Math spans auto-detect and inject KaTeX CDN — no manual setup.
10. **Deterministic Font Loading**: Font families auto-quoted; `document.fonts.ready` awaited before screenshots.
11. **Overflow Is a Hard Failure**: DOM-based overflow detection fails + retries any clipped text.
12. **Fail-Closed Auth**: `x-api-key` required on all API routes (401 if `API_KEYS` unset) + per-key Redis token-bucket rate limiting.
13. **Render Service Is Internal**: Playwright is not published to the host; it requires `RENDER_SERVICE_KEY` and runs with same-origin security enabled.
14. **SSRF-Guarded Image Fetch**: The worker validates every image URL (block loopback/link-local/metadata, allow LAN, size/redirect caps).
15. **Sanitized LLM/Edited HTML**: Designer output and rerender payloads pass through the HTML sanitizer before rendering/saving.
16. **Ephemeral Artifacts**: Files persist until the hourly TTL sweep removes the output directory and task row; downloads are repeatable, `?consume=true` opts into delete-after-delivery (ADR-0007).
17. **Manual Edit → Re-render**: `POST /tasks/{id}/formats/{fmt}/rerender` renders edited HTML without the designer LLM; vision audit is opt-in (ADR-0010).
18. **Template-First Composition**: Human-authored Jinja2 templates are tried before the LLM designer; the LLM falls back only on no-match or overflow. Templates carry `data-slot` attributes enabling a two-way promote loop (ADR-0011).

## Docker & Deployment

- `backend/Dockerfile` — API/worker/beat image: `python:3.12-slim`, deps pinned in `pyproject.toml`/`requirements.txt`, **no** `playwright` package (rendering goes over HTTP to the render service).
- `backend/Dockerfile.playwright` — render service: `python:3.12-slim-bookworm` + only the **chromium headless shell** (`--only-shell`), browsers at `/ms-playwright`. ~1.2GB vs 3.6GB for the official image.
- `frontend/Dockerfile` — Node build stage → static `dist/`, staged into a shared `frontend-dist` volume that the API mounts at `/app/static` and serves (SPA fallback).
- `backend/.dockerignore` — excludes `.venv`, `data/`, `tests/`, `tailwindcss` from the build context.
- `docker-compose.yml` — healthchecks on all services, API runs `--workers 2`, worker waits for Playwright healthy, `beat` runs the hourly retention sweep, config + data bind-mounted for config-driven control, Playwright has **no host port**.
- Runtime SQLite DB (`backend/data/tasbir.db`) and `backend/data/output/` are gitignored and recreated on boot.
10. **Image Embedding**: Images downloaded and base64-embedded into HTML at pipeline runtime.
