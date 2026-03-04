# Social Media Asset Pipeline Worker

A Cloudflare Worker that turns blog content into platform-ready social assets (captions + images) for:

- Instagram post (1080x1080)
- Instagram story (1080x1920)
- Carousel slides (1080x1080)
- Twitter/X card (1200x630)
- LinkedIn post (1200x627)

This project is fully config-driven:

- all layout templates live in `templates/**/*.html`
- all behavior is controlled from `config/pipeline/*.yaml` (via `config/pipeline.config.yaml` entrypoint)
- runtime reads generated assets from `src/generated/template-assets.ts`

No template rendering logic is hardcoded per design.
`design_system` in `config/pipeline/design.yaml` is the canonical source; build-time projection keeps legacy keys compatible.

## What You Get

- AI-generated social copy (`instagram_caption`, `twitter_caption`, `linkedin_caption`)
- AI-selected `template_style`, `post_archetype`, and `font_profile`
- Slot-based template filling (`slot_content` + user overrides)
- Optional background-image sourcing (feature/stock/AI/custom) with HTML-based decorative layers
- PNG rendering through Cloudflare Browser Rendering + upload to R2

## HTML vs `htmlx`

Use `.html` templates.

- `.html` is the web standard and works with all tooling
- `htmlx` is not a standard HTML template format
- if you mean `htmx`, it still uses normal `.html` files

## Project Layout

- `config/pipeline.config.yaml`: composed config entrypoint (`extends` fragments)
- `config/pipeline/design.yaml`: central `design_system` (tokens, render presets, styles, formats, templates)
- `config/pipeline/content.yaml`: archetypes, slot schema, generation prompts/limits
- `config/pipeline/runtime.yaml`: runtime, feature flags, security, storage
- `templates/**/*.html`: visual templates using token and slot placeholders
- `scripts/embed-template-assets.mjs`: validates YAML + embeds template files into generated TypeScript
- `src/generated/template-assets.ts`: generated runtime config/template bundle (do not edit manually)
- `src/index.ts`: Worker routes + orchestration pipeline
- `src/templates.ts`: template selection, token interpolation, slot resolution
- `src/design-system.ts`: typography, color tokens, and render controls

## Prerequisites

- Node.js 20+
- pnpm 9+
- Cloudflare account
- Workers AI enabled
- Browser Rendering enabled
- R2 bucket created
- Ghost Content API key (or use `/generate-from-content` for direct content)

## Quick Start

1. Install dependencies:

```bash
pnpm install
```

2. Build generated assets (required after config/template/style changes):

```bash
pnpm run build:assets
```

3. Configure local environment:

```bash
cp .dev.vars.example .dev.vars
```

4. Fill required vars in `.dev.vars`:

- `GHOST_API_URL`
- `GHOST_CONTENT_API_KEY`
- `API_KEYS` (comma-separated accepted API keys)

5. Start local dev server:

```bash
pnpm run dev
```

6. Check health route:

```bash
curl http://127.0.0.1:8787/health
```

If your local port differs, use the port printed by Wrangler.

## First End-to-End Test

Generate assets directly from provided content (no Ghost fetch required):

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Ship Social Content Faster",
    "content": "A repeatable process helps teams publish consistent social posts.",
    "templateStyle": "editorial",
    "postArchetype": "insight",
    "fontProfile": "editorial-serif"
  }'
```

You should receive:

- `llm_output` (captions, hashtags, style/archetype/font, slots)
- `assets` keys for each format
- optional public URLs if `R2_PUBLIC_BASE_URL` is configured

## Render Templates Locally

Use this when you want to test template visuals quickly without running full `/generate`.

1. Start local dev:

```bash
pnpm run build:assets
pnpm run dev -- --port 8787
```

2. In another terminal, resolve a local API key from `.dev.vars`:

```bash
API_KEY=$(grep '^API_KEYS=' .dev.vars | head -n1 | sed 's/^API_KEYS=//' | sed 's/^\"//;s/\"$//' | cut -d',' -f1 | xargs)
```

3. Render one template HTML (example: Twitter editorial):

```bash
curl "http://127.0.0.1:8787/template/twitter-card?templateId=twitter-card/editorial&templateStyle=editorial&templateArchetype=insight&title=Why%20Async%20Product%20Updates%20Build%20Trust&caption=Teams%20build%20trust%20when%20updates%20focus%20on%20decisions%20and%20outcomes.&brandName=Tasbir%20Blog&brandingColor=%231f7a8c" \
  -H "x-api-key: $API_KEY" \
  > /tmp/twitter-editorial.html
```

4. Optional: create a PNG from the rendered HTML with headless Chrome:

```bash
google-chrome-stable \
  --headless=new \
  --disable-gpu \
  --hide-scrollbars \
  --window-size=1200,630 \
  --virtual-time-budget=3500 \
  --screenshot=/tmp/twitter-editorial.png \
  "file:///tmp/twitter-editorial.html"
```

### Render Every Registered Template

```bash
mkdir -p /tmp/template-previews/html
curl -sS "http://127.0.0.1:8787/template-catalog" -H "x-api-key: $API_KEY" > /tmp/template-previews/catalog.json

jq -c '.templates[]' /tmp/template-previews/catalog.json | while read -r t; do
  id=$(printf '%s' "$t" | jq -r '.id')
  format=$(printf '%s' "$t" | jq -r '.format')
  style=$(printf '%s' "$t" | jq -r '.style')
  archetype=$(printf '%s' "$t" | jq -r '.archetypes[0] // "insight"')
  file="/tmp/template-previews/html/${id//\//__}.html"
  curl -sS "http://127.0.0.1:8787/template/${format}?templateId=$(printf '%s' "$id" | jq -sRr @uri)&templateStyle=$(printf '%s' "$style" | jq -sRr @uri)&templateArchetype=$(printf '%s' "$archetype" | jq -sRr @uri)&title=Local%20Template%20Preview&caption=Visual%20check%20for%20layout%20and%20readability.&brandName=Tasbir%20Blog&brandingColor=%231f7a8c" \
    -H "x-api-key: $API_KEY" > "$file"
done
```

This produces one `.html` per template ID under `/tmp/template-previews/html`.

## API Routes

- `GET /health`
- `GET /template/<format>` preview renderer (API key required)
- `GET /template-catalog` test catalog for styles/templates/versions (API key required)
- `POST /generate` fetches Ghost post by `slug` or `url` (API key required)
- `POST /generate-from-content` uses direct title/content payload (API key required)
- `POST /webhook/ghost` webhook-triggered generation (`x-webhook-token` required)

Authenticated routes accept:

- `x-api-key: <one of API_KEYS>`
- or `Authorization: Bearer <one of API_KEYS>`

See [API Reference](docs/api-reference.md) for full request/response examples.

## Template Selection Behavior

For each format, template resolution order is:

1. explicit `templateIds[format]` from request
2. `templateStyle + postArchetype`
3. `postArchetype`
4. `templateStyle`
5. `formats.<format>.default_template_id`

Font profile resolution order is:

1. explicit request `fontProfile`
2. model output `font_profile`
3. `typography.selection.by_style`
4. `typography.selection.by_archetype`
5. `typography.default_font_profile`

## Core Runtime Overrides (Per Request)

You can override generation behavior in request payload:

- `templateStyle`, `postArchetype`, `fontProfile`
- `templateIds` per format
- `slotOverrides` for direct slot control
- `brandingColor`, `brandName`
- `brandTokens` (fine-grained color token overrides)
- `design` (preset/alignment/opacity/layout controls)
- `storage` (overwrite/versioned path behavior)
- `output` (choose `formats` and `carouselSlides`)
- `llm` (system prompt/instructions/temperature/maxTokens overrides)
- `image` (choose `auto|none|feature|stock|ai|custom`, plus `customUrl` and prompt controls)

## Environment Variables

Required:

- `GHOST_API_URL`
- `GHOST_CONTENT_API_KEY`
- `API_KEYS`
- `GHOST_WEBHOOK_TOKEN` (required for `/webhook/ghost`)

Optional:

- `R2_PUBLIC_BASE_URL`
- `PEXELS_API_KEY`
- `GHOST_WEBHOOK_TOKEN`
- `NOTIFY_WEBHOOK_URL`
- `NOTIFY_HOST_ALLOWLIST`
- `IMAGE_HOST_ALLOWLIST`
- `ALLOW_PRIVATE_NETWORK_TARGETS`
- `DEFAULT_BRAND_COLOR`
- `BRAND_NAME`
- `LLM_MODEL`
- `IMAGE_MODEL`
- `R2_KEY_PREFIX`
- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOWED_HEADERS`
- `CORS_ALLOW_CREDENTIALS`
- `CORS_MAX_AGE_SECONDS`

## Daily Development Commands

```bash
pnpm run build:assets    # rebuild generated runtime assets
pnpm run check           # type-check
pnpm run test            # run tests
pnpm run dev             # local worker
pnpm run deploy          # deploy to Cloudflare
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [Architecture](docs/architecture.md)
- [Template System](docs/template-system.md)
- [Config Reference](docs/config-reference.md)
- [Design Principles](docs/design-principles.md)
- [Research Summary](docs/research-summary.md)
- [Troubleshooting](docs/troubleshooting.md)
