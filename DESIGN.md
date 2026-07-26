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

## Data Flow & Parallel Agent Architecture

### Generation Pipeline Flow

```
Ghost Webhook / UI Request
         │
         ▼
  ┌──────────────┐
  │  FastAPI      │  Validates request, creates Celery task
  │  POST /generate │  Returns { task_id } immediately
  └──────┬───────┘
         │ Subscribe to SSE /tasks/{id}/stream
         ▼
  ┌──────────────┐
  │  Celery Worker │  Runs LangGraph state machine pipeline
  │  generate_task │
  └──────┬───────┘
         │
    ┌────┴────┐
    │ LangGraph │
    │ Pipeline │
    └────┬────┘
         │
    ┌────┴────────┐
    │Strategist   │  Aura Vance (Chief Content Strategist)
    │Node 1       │  Deconstructs content & formulates Strategic Brief
    └────┬────────┘
         │
         ├────────────────────────────────────────┐ (Parallel Fan-out)
         ▼                                        ▼
    ┌────┴────────┐                          ┌────┴────────┐
    │Copywriter   │  Julian Sterling         │Visual Dir.  │  Elena Rostova
    │Node 2       │  Generates copy          │Node 3       │  Selects background
    │(Parallel)   │  for all formats         │(Parallel)   │  for all formats
    └────┬────────┘                          └────┬────────┘
         │                                        │
         └────────────────────────────────────────┘ (Fan-in to Designer)
                               │
                               ▼
                        ┌────┴────────┐
                        │Designer     │  Marcus Chen (UI/UX Developer)
                        │Node 4       │  Generates standalone HTML visual canvas
                        └────┬────────┘  using dynamic DB formats & Tailwind
                             │
                             ▼
                        ┌────┴────────┐
                        │Quality Check│  Victoria Thorne (Quality Director)
                        │Node 5       │  Validates layout integrity & contrast
                        └────┬────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼ (Passed score >= 50)             ▼ (Failed score < 50, retry <= 2)
  ┌──────────────────┐               ┌──────────────────┐
  │ Playwright Render│               │ Designer Retry   │
  │ Node 6           │               │ Refinement       │
  └─────────┬────────┘               └──────────────────┘
            │
            ▼
  ┌──────────────────┐
  │ MinIO Asset Store│  PNG upload & SSE completion event
  └──────────────────┘
```

## Core Design & Technical Constraints

1. **Pure Standalone Visual Graphic Canvas**:
   - Assets are visual graphic cards, posters, or artwork image canvases.
   - Website navigation bars (`<nav>`), landing page layouts, URL chrome, and interactive `<button>` elements are prohibited.
2. **Strict No-Emoji Rule**:
   - Raw Unicode emojis are forbidden in visual copy and graphics.
   - Enforced by system prompts and `remove_emojis()` in `backend/app/services/cleanup.py`.
3. **Dynamic Database Format Lookup**:
   - `get_format_info(fmt_id)` fetches user-created format dimensions (`width`, `height`), names, and narrative instructions from the PostgreSQL `Format` table and injects them into user prompts.
4. **Intra-Node Format Concurrency**:
   - Multiple requested formats are processed concurrently using `asyncio.gather()` inside agent nodes.

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
