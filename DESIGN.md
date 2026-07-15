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

## Data Flow

### Generation Flow

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
  │  Celery Worker │  Runs LangGraph pipeline
  │  generate_task │
  └──────┬───────┘
         │
    ┌────┴────┐
    │ LangGraph │  State machine with 5 nodes
    │  Pipeline │
    └────┬────┘
         │
    ┌────┴────┐
    │Node 1:  │  Gemini 2.0 Flash
    │Strategist│  "Analyze content, plan campaign angles"
    └────┬────┘
         │
    ┌────┴────┐
    │Node 2:  │  Gemini 2.0 Flash
    │Copywriter│  "Write per-format copy"
    └────┬────┘
         │
    ┌────┴────┐
    │Node 3:  │  Gemini 2.0 Flash
    │Visual   │  "Choose background style, map tokens"
    │Director │
    └────┬────┘
         │
    ┌────┴────┐
    │Node 4:  │  Gemini 2.0 Flash
    │Designer │  "Generate HTML with Tailwind + tokens"
    └────┬────┘
         │
    ┌────┴────┐
    │Node 5:  │  Gemini 2.0 Flash
    │Quality  │  "Validate output, pass/fail"
    └────┬────┘
         │ Loop back to Designer if failed (max 2 retries)
         ▼
  ┌──────────────┐
  │  Playwright   │  Screenshots HTML → PNG
  │  Render       │  Stores in MinIO
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  Penpot MCP   │  (Optional) Push tokens + frames
  │  Publish      │  to Penpot for designer refinement
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │    SSE       │  "complete" event → UI gets results
  │  Notify      │
  └──────────────┘
```

## Agent State Machine (LangGraph)

```python
class GenerationState(TypedDict):
    # Input
    content: str
    title: str
    excerpt: str
    tags: list[str]
    brand: dict
    campaign: dict
    requested_formats: list[str]
    content_type: str

    # Agent outputs (populated by each node)
    strategic_brief: str
    copy_by_format: dict[str, str]
    background_by_format: dict[str, BackgroundStyle]
    design_tokens: dict
    html_by_format: dict[str, str]
    slot_values_by_format: dict[str, dict]

    # Quality
    quality_score: int
    quality_issues: list[str]

    # Rendering
    assets_by_format: dict[str, str]  # format → MinIO key

    # Flow control
    refinement_count: int
    max_refinements: int  # default 2
    next_node: str
```

## Background Generation (Zero Cost)

Images are the hardest cost to eliminate. Strategy:

### Tier 1: CSS Gradients (Default — Always Free)

```python
GRADIENT_PRESETS = {
    "sunset": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "ocean": "linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)",
    "forest": "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)",
    "fire": "linear-gradient(135deg, #f12711 0%, #f5af19 100%)",
    "corporate": "linear-gradient(135deg, #2c3e50 0%, #3498db 100%)",
    "minimal": "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
}
```

### Tier 2: SVG Patterns (Always Free)

```python
def generate_dot_grid(color: str, size: int = 20) -> str:
    return (
        f"background-color: {color};"
        f"background-image: radial-gradient(circle, "
        f"{color}15 1px, transparent 1px);"
        f"background-size: {size}px {size}px;"
    )
```

### Tier 3: Unsplash Photos (Free, 1,000 req/hr)

```python
async def search_unsplash(query: str) -> str | None:
    """Get free stock photo URL. Requires attribution in output."""
    # GET https://api.unsplash.com/search/photos?query=...
    # Returns regular (1080px) URL
```

## Design Token System

### DTCG Format (W3C Standard)

All tokens stored in DTCG (Design Tokens Community Group) format:

```json
{
  "tasbir": {
    "color": {
      "$type": "color",
      "primary": { "$value": "#0066cc" },
      "surface": { "$value": "#ffffff" },
      "text": { "$value": "#1a1a1a" }
    },
    "typography": {
      "$type": "fontFamily",
      "heading": { "$value": "Inter" },
      "body": { "$value": "Inter" }
    },
    "spacing": {
      "$type": "dimension",
      "sm": { "$value": "8px" },
      "md": { "$value": "16px" },
      "lg": { "$value": "32px" }
    }
  }
}
```

### Token Flow

```
Penpot (authoring tool)
   │ Create/edit tokens visually
   │ Webhook: tokens changed
   ▼
Tasbir /webhook/penpot
   │ Export DTCG format via MCP
   │ Store in PostgreSQL
   ▼
Generation Pipeline
   │ Fetch tokens from DB
   │ Convert to Tailwind config
   │ Inject into HTML
   ▼
Rendered Post
   │ Uses tokens for colors, fonts, spacing
```

## Prompt Management System

All AI prompts stored in `prompt_registry` table (not hardcoded):

```sql
CREATE TABLE prompt_registry (
    name        TEXT PRIMARY KEY,        -- 'strategist', 'copywriter', etc.
    version     INTEGER DEFAULT 1,
    system_prompt TEXT NOT NULL,
    user_template TEXT,                  -- Optional template with {slots}
    temperature  FLOAT DEFAULT 0.7,
    max_tokens   INTEGER DEFAULT 2000,
    is_active    BOOLEAN DEFAULT true,
    updated_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE prompt_versions (
    id           UUID PRIMARY KEY,
    prompt_name  TEXT REFERENCES prompt_registry(name),
    version      INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL
);
```

API allows viewing, editing, and rollback:

```
GET  /prompts              → List all prompts
GET  /prompts/{name}       → Get active prompt
PUT  /prompts/{name}       → Update prompt (creates new version)
POST /prompts/{name}/restore → Rollback to previous version
```

## API Design Principles

1. **Every response includes `task_id`** — generation is always async
2. **SSE for streaming** — real-time progress without polling
3. **Pydantic v2 for validation** — every endpoint has request/response models
4. **API key auth** — simple `x-api-key` header
5. **Rate limiting via Redis** — distributed, not in-memory

## Security

- API authentication: `x-api-key` header
- Rate limiting: Redis-backed, configurable per-route
- CORS: Configurable origins (default: all)
- Webhook verification: HMAC-SHA256 signatures
- No secrets in code: all through environment variables
- Penpot tokens: Access token authentication

## Database Schema (Key Tables)

```sql
-- Core storage
settings          (id, data JSONB, updated_at)           -- Singleton
templates         (id, name, html, slots JSONB, enabled, ...)
formats           (id TEXT PK, width, height, name, ai_instruction)
design_tokens     (id, name, data JSONB, version)
generation_tasks  (id, celery_task_id, status, source_data JSONB, result JSONB)
assets            (key TEXT PK, task_id, format, content_type, size_bytes)
edited_content    (id, slug, format, html, slot_values JSONB, UNIQUE slug+format)
prompt_registry   (name TEXT PK, version, system_prompt, ...)
prompt_versions   (id, prompt_name, version, system_prompt)
```

## Docker Services

| Service | Image | Mem Limit | Port |
|---|---|---|---|
| postgres | postgres:16-alpine | 512MB | 5432 |
| redis | redis:7-alpine | 128MB | 6379 |
| minio | minio/minio | 256MB | 9000, 9001 |
| api | Dockerfile.api | 256MB | 8000 |
| worker | Dockerfile.worker | 512MB | - |
| playwright | mcr.microsoft.com/playwright/python:v1.52 | 1.5GB | 4000 |
| penpot | penpotapp/penpot:latest | 1GB | 9001 |
| ui | Dockerfile.ui | 128MB | 5173 |
| caddy | caddy:alpine | 64MB | 80, 443 |

## Cost Breakdown ($0 Goal)

| Item | How it's free |
|---|---|
| Gemini 2.0 Flash | Google AI Studio free tier (unlimited, 30 req/min) |
| Gemini 2.5 Flash | Google AI Studio free tier (1,500 req/day) |
| Backgrounds | CSS gradients + SVG patterns (code-generated, $0) |
| Photos | Unsplash API (free, 1,000 req/hr in production) |
| Hosting | Oracle Cloud free tier or Hetzner $5.99/mo |
| Database | PostgreSQL in Docker ($0) |
| Storage | MinIO in Docker ($0) |
| Browser | Playwright in Docker ($0) |
| Design Tool | Penpot self-hosted ($0) |
| SSL/Domain | Let's Encrypt + DuckDNS ($0) |

## Monitoring

- Health check: `GET /health` (DB, Redis, MinIO, Playwright status)
- Task tracking: `generation_tasks` table with status + error
- Logging: Structured JSON logs via `structlog`
- Optional: Self-hosted Grafana + Loki for log aggregation
