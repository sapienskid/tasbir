# Tasbir v3 — Project Plan

AI-powered social media asset pipeline. Zero API costs.
Self-hosted via Docker, HTML + PNG output.

## Mission

Convert blog content into platform-optimized social media designs using a
multi-agent AI pipeline. Outputs HTML files (opened in any browser) and
PNG renders (ready to share), with no separate storage or UI needed.

## Core Principles

1. **HTML + PNG output** — Generated designs are standalone HTML files with CSS
   variables, rendered to PNG via Playwright for visual verification.
2. **Zero API costs** — Gemini free tier, CSS backgrounds, free embeddings
3. **Self-hosted** — Docker, no SaaS dependencies
4. **YAML design system** — Tokens, brand, platforms, and campaigns in YAML files
5. **Human-editable** — User opens HTML in browser, tweaks CSS, re-renders
6. **Minimal infrastructure** — SQLite for task tracking, no MinIO, no separate UI
7. **Multi-agent pipeline** — LangGraph with agent nodes (Strategist → Copywriter → Designer → Verifier) + a deterministic Renderer

## Architecture Summary

```
n8n Webhook → FastAPI → Celery + Redis → LangGraph Pipeline → HTML + PNG
    │                                                           │
    └────────── polls GET /tasks/{id} for status ──────────────┘
                                                  Files in data/output/{task_id}/
                                                  (.html for review, .png for sharing)
```

## Phase Progress

### Phase 1: Foundation — Docker + API
- [x] `docker-compose.yml` with core services (API, worker, Redis, Playwright)
- [x] FastAPI app skeleton with health check
- [x] SQLite for task tracking
- [x] Celery + Redis for background task processing

### Phase 2: Data Layer — Minimal Models
- [x] `generation_tasks` table (SQLite) — id, status, source_data, result, error
- [x] `audit_logs` table (SQLite) — per-agent decisions, verifier critiques
- [x] API: `POST /generate`, `GET /tasks/{id}`, `GET /health`
- [x] YAML prompt configs (`backend/config/prompts/*.yaml`)

### Phase 3: YAML Design System
- [x] `brand.yaml` — Brand identity (name, tagline, mission, story, social, footer, categories)
- [x] `tokens.yaml` — CSS variable → value mappings (grayscale palette + 3 font voices)
- [x] `platforms.yaml` — Platform dimensions
- [x] `campaigns.yaml` — Campaign presets (tone, ground, language)
- [x] `design-instruction.yaml` — Swiss typographic style (type roles, measure, layout archetypes)

### Phase 4: Agent Pipeline — LangGraph Multi-Agent
- [x] **Strategist** (Aura Vance) — content analysis → structured brief + category + ground
- [x] **Copywriter** (Julian Sterling) — brief → structured copy per platform
- [x] **Designer** (Marcus Chen) — copy + brand + campaign + images → HTML with CSS variables
- [x] **Renderer** — injects tokens/fonts/KaTeX/images deterministically, saves HTML
- [x] **Verifier** (Victoria Thorne) — deterministic checks + overflow detection, render to PNG,
      multimodal audit via Gemini Vision, retry loop on failure

### Phase 5: Integration
- [ ] n8n workflow: Ghost webhook → Tasbir API
- [x] User workflow: open HTML in browser → tweak CSS → re-render
- [x] Status endpoint for n8n polling
- [x] Docker Compose finalization (healthchecks, baked images, slim render image)

### Phase 6: Polish
- [x] Comprehensive test suite
- [x] Documentation (AGENTS.md, DESIGN.md, docs/adr, docs/glossary)
- [x] YAML prompt tuning
- [x] Rate limit optimization for Gemini free tier (serialized vision calls)
- [x] Docker image slimming (~55% smaller stack; chromium headless shell only)
- [ ] Mermaid diagram rendering support

## What Was Removed From v2

| Removed | Replaced By |
|---------|-------------|
| PostgreSQL (app DB) | SQLite |
| MinIO | Files on disk (HTML, PNG) |
| SvelteKit UI | n8n triggers + HTML/PNG output |
| Socket.IO | n8n polls REST API for status |
| Tailwind CLI | Clean CSS in HTML, no Tailwind compilation |
| Prompt DB tables | YAML files in `config/prompts/` |
| Templates DB table | LLM generates from scratch (no template files) |
| Brands DB table | `brand.yaml` |
| DesignTokens DB table | `tokens.yaml` |
| Formats DB table | `platforms.yaml` |
| Settings DB table | Removed (not needed) |
| Ghost SDK | n8n handles Ghost webhooks |
| Design tool service | Removed (HTML + PNG output opens in any browser) |
| HTML-to-design-file converter | Removed (Verifier renders HTML → PNG via Playwright) |
