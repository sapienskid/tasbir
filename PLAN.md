# Tasbir v2 — Project Plan

A fully agentic, Python-based social media asset pipeline. Zero API costs.
Self-hosted via Docker, no Cloudflare dependencies.

## Mission

Convert blog content into platform-optimized social media images using a
multi-agent AI pipeline — completely free to run, with Penpot for design
token management and human-in-the-loop refinement.

## Core Principles

1. **Zero API costs** — Gemini free tier, CSS gradients, Unsplash free tier
2. **Self-hosted** — Everything in Docker, no SaaS dependencies
3. **Design token driven** — Penpot as source of truth for all visual tokens
4. **Agentic** — LangGraph state machine with tool-using agents
5. **Async by default** — Celery tasks, SSE streaming, webhook triggers

## Phases

### Phase 1: Foundation — Docker + Basic API (Week 1)

- [ ] `docker-compose.yml` with all services
- [ ] FastAPI app skeleton with health check
- [ ] PostgreSQL schema + Alembic migrations
- [ ] Redis + Celery configuration
- [ ] MinIO for object storage
- [ ] Caddy reverse proxy with auto HTTPS

### Phase 2: Data Layer — Models + API Routes (Week 2)

- [ ] SQLAlchemy models (settings, templates, tasks, assets, prompts)
- [ ] CRUD API for settings
- [ ] CRUD API for templates
- [ ] CRUD API for design tokens
- [ ] CRUD API for output formats
- [ ] CRUD API for prompts (prompt registry)
- [ ] Task tracking (status, results, error handling)

### Phase 3: AI Layer — LLM Service + Backgrounds (Week 2-3)

- [ ] Google Gemini client (free tier via AI Studio)
- [ ] LiteLLM integration (fallback to OpenRouter if needed)
- [ ] Background service: CSS gradients + SVG patterns (zero cost)
- [ ] Background service: Unsplash API (free stock photos)
- [ ] Background service: Solid colors + geometric patterns

### Phase 4: Agent Engine — LangGraph Pipeline (Week 3-4)

- [ ] `prompt_registry` table — all prompts stored in DB, versioned
- [ ] **Strategist agent**: content analysis, campaign planning
- [ ] **Copywriter agent**: per-format copy generation
- [ ] **Visual Director agent**: background selection, token mapping
- [ ] **Designer agent**: HTML generation with Tailwind + tokens
- [ ] **Quality agent**: output validation, refinement loop
- [ ] State machine with checkpointing + error recovery

### Phase 5: Rendering + Storage (Week 4)

- [ ] Playwright HTTP service (HTML → PNG)
- [ ] Playwright connection pooling for performance
- [ ] MinIO asset storage and retrieval
- [ ] Asset URL generation with caching

### Phase 6: Ghost + Penpot Integration (Week 5)

- [ ] Ghost webhook handler (`post.published` → auto-generate)
- [ ] Ghost Admin API client (JWT auth, fetch full content)
- [ ] Penpot MCP client (read/write design tokens)
- [ ] DTCG token format conversion (internal ↔ W3C standard)
- [ ] Bidirectional token sync service
- [ ] Penpot webhook handler (token changes → re-render)

### Phase 7: Frontend — SvelteKit + shadcn-svelte (Week 5-7)

- [ ] SvelteKit project with TypeScript
- [ ] shadcn-svelte component library setup
- [ ] Dashboard page (recent tasks, quick generate)
- [ ] Generate page (content input, format selection, progress)
- [ ] Settings page (brand, campaign, formats)
- [ ] Templates page (browse, create, edit templates)
- [ ] Tokens page (view/sync design tokens from Penpot)
- [ ] Tasks page (history, status, results)
- [ ] SSE streaming for real-time generation progress

### Phase 8: Deployment + Polish (Week 7-8)

- [ ] Production Docker Compose configuration
- [ ] Resource limits for each service
- [ ] Seed script (default formats, prompts, settings)
- [ ] Backup and restore procedures
- [ ] Health monitoring (Grafana + Loki)
- [ ] Tests (pytest backend, Vitest frontend)
- [ ] README with full setup guide

## File Creation Order

```
Phase 1:   docker-compose.yml → .env.example → .gitignore
Phase 1:   backend/pyproject.toml → backend/app/main.py → backend/app/config.py
Phase 1:   backend/app/core/security.py → backend/app/db/session.py → alembic.ini

Phase 2:   backend/app/models/*.py → backend/app/db/repositories/*.py
Phase 2:   backend/app/api/*.py → backend/app/tasks/celery_app.py

Phase 3:   backend/app/services/llm.py → backend/app/services/backgrounds.py
Phase 3:   backend/app/services/unsplash.py

Phase 4:   backend/app/agents/prompts/registry.py
Phase 4:   backend/app/agents/orchestrator/graph.py
Phase 4:   backend/app/agents/orchestrator/nodes/*.py
Phase 4:   backend/app/agents/orchestrator/tools/*.py

Phase 5:   backend/app/services/renderer.py → backend/app/services/storage.py
Phase 5:   backend/app/tasks/generate.py

Phase 6:   backend/app/services/penpot.py → backend/app/services/token_exchange.py
Phase 6:   backend/app/services/token_sync.py → backend/app/api/webhooks/*.py

Phase 7:   ui/package.json → ui/svelte.config.js → ui/vite.config.ts
Phase 7:   ui/src/lib/components/ui/* → ui/src/routes/*

Phase 8:   scripts/seed.py → scripts/migrate.sh → README.md
```

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| AI text | Gemini 2.0/2.5 Flash via Google AI Studio | Free tier, unlimited requests |
| Agent framework | LangGraph | State machine, tool use, checkpointing |
| UI | SvelteKit + shadcn-svelte | Fastest compiled framework, beautiful components |
| Design tool | Penpot (self-hosted) | Open source, MCP server, DTCG tokens |
| Task queue | Celery + Redis | Mature, reliable, distributed |
| Backgrounds | CSS gradients + SVG patterns | Zero cost, professional quality |
| Photos | Unsplash API | Free, 1,000 req/hr in production |
| Browser render | Playwright (Docker) | Self-hosted, no API costs |
