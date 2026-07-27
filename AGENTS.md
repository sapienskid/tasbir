# Tasbir v2 — Agent Guide

This file tells AI coding agents everything they need to work on this project.
Read this first before making any changes.

## Project Identity

- **Name**: Tasbir ("depiction" in Arabic)
- **Purpose**: AI-powered social media asset generation pipeline
- **Stack**: Python (FastAPI, LangGraph, Celery) + SvelteKit + Docker
- **Cost target**: Zero API costs (Gemini free tier + CSS backgrounds + Unsplash)

## Agent Architecture Overview

The Tasbir agent system operates as an elite agency design studio team. The pipeline runs **SERIALLY** (one node at a time) to respect Gemini free tier rate limits. Within each node, multiple formats are processed **in parallel** via `asyncio.gather()` with semaphores:

```
User / Ghost CMS / Webhook → FastAPI API → Celery Task Queue → LangGraph Agent Pipeline
                                                                        │
                                                               ┌────────┴────────┐
                                                               │   Strategist    │  (Serial — 1 call)
                                                               │  (Aura Vance)   │
                                                               └────────┬────────┘
                                                                        │
                                                               ┌────────┴────────┐
                                                               │   Copywriter    │  (Serial node, parallel formats via Semaphore(3))
                                                               │ (Julian Sterling)│
                                                               └────────┬────────┘
                                                                        │
                                                               ┌────────┴────────┐
                                                               │ Visual Director │  (Serial node, parallel formats via Semaphore(3))
                                                               │ (Elena Rostova) │
                                                               └────────┬────────┘
                                                                        │
                                                               ┌────────┴────────┐
                                                               │    Designer     │  (Serial node, parallel formats via Semaphore(2))
                                                               │  (Marcus Chen)  │
                                                               └────────┬────────┘
                                                                        │
                                                               ┌────────┴────────┐
                                                               │  Quality Check  │  (LLM-based audit with programmatic fallback)
                                                               │(Victoria Thorne)│
                                                               └──────┬──┬───────┘
                                                                      │  │
                                                    ┌─────────────────┘  └─────────────────┐
                                                    ▼ (Passed)                             ▼ (Failed, retry <=2)
                                             ┌──────────────┐                    ┌──────────────┐
                                             │   Renderer   │                    │   Designer   │
                                             │(Playwright)  │                    │  (Refinement)│
                                             └──────┬───────┘                    └──────────────┘
                                                    │
                                                    ▼
                                              MinIO Storage
```

**Rate limiting notes**:
- Each node uses `asyncio.Semaphore(N)` to limit concurrent LLM calls: copywriter=3, visual_director=3, designer=2, renderer=2
- Nodes are serial in the graph to avoid hitting Gemini TPM limits on free tier
- `call_llm_with_retry()` handles 429 rate limit errors with exponential backoff

## Agent Personas & Studio Roles

All agent prompts are managed in `backend/app/agents/prompts/` and stored in the database (`prompt_registry` table):

| Agent | Persona & Role | Description |
|---|---|---|
| **Strategist** | Aura Vance (Chief Brand Strategist) | Analyzes input content, target audience, emotional hooks, brand tone — produces Strategic Brief. |
| **Copywriter** | Julian Sterling (Lead Brand Wordsmith) | Per-format structured copy (Headline, Subhead, Key Points, Badge, Tagline). No emojis. |
| **Visual Director** | Elena Rostova (Senior Art Director) | Background selection: CSS gradients, SVG patterns, Unsplash photos. Uses `generate_background_tool`, `search_unsplash`. |
| **Designer** | Marcus Chen (Senior UI/UX Creative Developer) | Generates standalone HTML posters with Tailwind CSS. Design tokens injected via server-side CSS compilation. |
| **Quality Check** | Victoria Thorne (Design Quality Director) | LLM-based design audit with programmatic fallback. Checks contrast, layout, placeholders. |
| **Token Generator** | Dr. Soren Lindqvist (Design System Architect) | LangGraph agent with 11 tools for full-spectrum DTCG token generation. Uses `check_contrast_tool` for WCAG AA validation. |

## Core System Directives & Constraints

1. **Pure Graphic Canvas (Not a Website UI)**:
   - Output must strictly be a visual artwork graphic, poster, or card canvas.
   - NO website landing pages, navigation headers (`<nav>`), search bars, hamburger menus, URL bars, or interactive `<button>` UI elements.
2. **Strict No-Emoji Rule**:
   - Raw Unicode emojis are forbidden in visual copy and graphic designs.
   - Enforced via system prompts and automated regex post-processing in `backend/app/services/cleanup.py` (`remove_emojis()`).
3. **Dynamic Database Format Injection**:
   - System prompts contain ZERO hardcoded formats or dimensions.
   - Format metadata (`name`, `width`, `height`, `ai_instruction`) is loaded dynamically from the database `Format` table via `app.services.formats.get_format_info()` and injected into user prompts.
4. **Intra-Node Format Concurrency**:
   - `copywriter`, `visual_director`, `designer`, and `renderer` nodes process multiple requested formats in parallel using `asyncio.gather()`.

## Directory Structure

```
tasbir/
├── PLAN.md                  ← Project plan & phases (CONSULT THIS FIRST)
├── AGENTS.md                ← This file — agent instructions
├── DESIGN.md                ← Architecture & design decisions
├── docker-compose.yml       ← All services orchestrated
├── .env.example             ← Required environment variables
│
├── backend/                 ← Python FastAPI backend
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── alembic.ini
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             ← FastAPI app entry point
│   │   ├── config.py           ← Pydantic Settings (env-based)
│   │   │
│   │   ├── api/                ← FastAPI route modules
│   │   │   ├── health.py       ← GET /health
│   │   │   ├── settings.py     ← CRUD /settings
│   │   │   ├── templates.py    ← CRUD /templates
│   │   │   ├── tokens.py       ← CRUD /tokens + generate
│   │   │   ├── formats.py      ← CRUD /formats
│   │   │   ├── generate.py     ← POST /generate (SSE stream)
│   │   │   ├── tasks.py        ← GET /tasks/{id}
│   │   │   ├── assets.py       ← GET /assets/{key}
│   │   │   ├── prompts.py      ← CRUD /prompts (registry)
│   │   │   └── webhooks/       ← Ghost + Penpot webhooks
│   │   │
│   │   ├── agents/             ← LangGraph agent definitions
│   │   │   ├── orchestrator/
│   │   │   │   ├── graph.py         ← Parallel State machine definition
│   │   │   │   ├── state.py         ← GenerationState TypedDict
│   │   │   │   ├── nodes/
│   │   │   │   │   ├── strategist.py
│   │   │   │   │   ├── copywriter.py
│   │   │   │   │   ├── visual_director.py
│   │   │   │   │   ├── designer.py
│   │   │   │   │   ├── quality_check.py
│   │   │   │   │   └── renderer.py
│   │   │   │   └── tools/
│   │   │   │       ├── search_templates.py
│   │   │   │       ├── search_unsplash.py
│   │   │   │       ├── generate_background.py
│   │   │   │       └── fetch_design_tokens.py
│   │   │   │
│   │   │   └── prompts/         ← Default prompt templates & personas
│   │   │       ├── registry.py  ← Prompt loading + versioning
│   │   │       ├── strategist.py
│   │   │       ├── copywriter.py
│   │   │       ├── visual_director.py
│   │   │       ├── designer.py
│   │   │       ├── quality_check.py
│   │   │       └── token_generator.py
│   │   │
│   │   ├── services/            ← Business logic
│   │   │   ├── llm.py           ← Gemini/LLM client
│   │   │   ├── formats.py       ← Dynamic database format service
│   │   │   ├── cleanup.py       ← Emoji stripping & button artifact cleanup
│   │   │   ├── backgrounds.py   ← CSS gradient + SVG pattern generator
│   │   │   ├── unsplash.py      ← Free stock photo client
│   │   │   ├── renderer.py      ← Playwright render client
│   │   │   ├── storage.py       ← MinIO/S3 client
│   │   │   ├── penpot.py        ← Penpot client
│   │   │   ├── token_exchange.py ← DTCG ↔ internal format
│   │   │   └── ghost.py         ← Ghost Admin API client
│   │   │
│   │   ├── db/                  ← Database & Repositories
│   │   └── tasks/               ← Celery task queue definitions
│   │
│   └── tests/                   ← pytest tests
│       ├── test_agents/         ← Prompt & graph tests
│       ├── test_api/            ← Route tests
│       └── test_services/       ← Cleanup, background & token tests
│
└── ui/                          ← SvelteKit frontend
```

## Common Tasks For AI Agents

### Adding a new agent persona or prompt
1. Create prompt module in `backend/app/agents/prompts/{name}.py`.
2. Register default prompt in `DEFAULT_PROMPTS` inside `backend/app/agents/prompts/registry.py`.
3. Add prompt to `scripts/seed.py`.
4. Add unit test in `backend/tests/test_agents/test_prompts.py`.

### Adding a new tool for agents
1. Create tool function in `backend/app/agents/orchestrator/tools/`.
2. Decorate with `@tool`.
3. Register in `orchestrator/tools/__init__.py`.
4. Add to the relevant agent node's tool list (`llm.bind_tools(_tools)`).

## Testing

- Backend: `cd backend && .venv/bin/python -m pytest`
- Frontend: `cd ui && vitest run`
