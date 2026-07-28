# Tasbir v3 — Project Plan

AI-powered social media asset pipeline. Zero API costs.
Self-hosted via Docker, Penpot-native output.

## Mission

Convert blog content into platform-optimized social media designs using a
multi-agent AI pipeline. Outputs native `.penpot` files — editable in Penpot,
with no separate storage or UI needed.

## Core Principles

1. **Penpot-native output** — Generated designs are valid `.penpot` files, fully editable
2. **Zero API costs** — Gemini free tier, CSS backgrounds, free embeddings
3. **Self-hosted** — Docker, no SaaS dependencies
4. **Design token driven** — Penpot Design System file is the single source of truth
5. **Human-editable** — User opens generated file in Penpot, tweaks, promotes to template
6. **Minimal infrastructure** — SQLite for task tracking, no MinIO, no separate UI
7. **Multi-agent pipeline** — LangGraph with 5 agents (Strategist → Copywriter → Designer → HTML→Penpot → Verifier)

## Architecture Summary

```
n8n Webhook → FastAPI → Celery + Redis → LangGraph Pipeline → .penpot file
    │                                                           │
    └────────── polls GET /tasks/{id} for status ──────────────┘
                                                    User opens in Penpot
                                                    (edit, review, promote)
```

## Phase Progress

### Phase 1: Foundation — Docker + API (v2, reworked for v3)
- [x] `docker-compose.yml` with core services (reduced for v3)
- [x] FastAPI app skeleton with health check
- [x] SQLite for task tracking (replaces PostgreSQL for app data)
- [x] Celery + Redis for background task processing
- [x] Caddy reverse proxy (optional, depends on deployment)

### Phase 2: Data Layer — Minimal Models
- [x] `generation_tasks` table (SQLite) — id, status, source_data, result, error
- [x] `audit_logs` table (SQLite) — per-agent decisions, verifier critiques
- [x] API: `POST /generate`, `GET /tasks/{id}`, `GET /health`
- [x] YakYAML prompt configs (`backend/config/prompts/*.yaml`)

### Phase 3: .penpot I/O Layer
- [x] `penpot_io.py` — Read/write `.penpot` files (ZIP + JSON)
- [x] Python library for `.penpot` schema (generate valid shapes, pages, tokens)
- [x] Design System file support & fallback tokens (`data/design_system/Tasbir Design System.penpot`)

### Phase 4: Agent Pipeline — LangGraph Multi-Agent
- [x] **Strategist** (Aura Vance) — content analysis → structured brief
- [x] **Copywriter** (Julian Sterling) — brief → structured copy per platform
- [x] **Designer** (Marcus Chen) — copy + templates → HTML with CSS variables
- [x] **HTML→Penpot Converter** (programmatic) — Playwright DOM extraction → .penpot shapes
- [x] **Verifier** (Victoria Thorne) — multimodal audit of rendered image via Gemini Vision

### Phase 5: Integration
- [ ] n8n workflow: Ghost webhook → Tasbir API
- [ ] User workflow: open .penpot in Penpot → edit → promote good designs to template
- [ ] Status endpoint for n8n polling
- [ ] Docker Compose finalization

### Phase 6: Polish
- [ ] Comprehensive test suite
- [ ] Documentation (AGENTS.md, DESIGN.md, this file)
- [ ] YAML prompt tuning
- [ ] Rate limit optimization for Gemini free tier

## What Was Removed From v2

| Removed | Replaced By |
|---------|-------------|
| PostgreSQL (app DB) | SQLite |
| MinIO | .penpot files (design IS the asset) |
| SvelteKit UI | n8n triggers + Penpot viewing/editing |
| Socket.IO | n8n polls REST API for status |
| Tailwind CLI | Clean CSS in HTML, no Tailwind compilation |
| Prompt DB tables | YAML files in `config/prompts/` |
| Templates DB table | Board pages in `.penpot` Design System file |
| Brands DB table | `.penpot` Design System file |
| DesignTokens DB table | `tokens.json` in `.penpot` Design System file |
| Formats DB table | Pages in `.penpot` Design System file |
| Settings DB table | Removed (not needed) |
| Ghost SDK | n8n handles Ghost webhooks |
| Token Generator agent | Penpot-native token management |
| Visual Director agent | Merged into Designer + Penpot templates |
