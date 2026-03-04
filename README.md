# Social Media Asset Pipeline Worker

A Cloudflare Worker that turns blog content into platform-ready social assets (captions + images) for:

- Instagram post (1080x1080)
- Instagram story (1080x1920)
- Carousel slides (1080x1080)
- Twitter/X card (1200x630)
- LinkedIn post (1200x627)

This project is fully config-driven:

- all layout templates live in `templates/**/*.html`
- all behavior is controlled from `config/pipeline.config.yaml`
- runtime reads generated assets from `src/generated/template-assets.ts`

No template rendering logic is hardcoded per design.

## What You Get

- AI-generated social copy (`instagram_caption`, `twitter_caption`, `linkedin_caption`)
- AI-selected `template_style`, `post_archetype`, and `font_profile`
- Slot-based template filling (`slot_content` + user overrides)
- Optional stock image lookup and AI image generation fallback
- PNG rendering through Cloudflare Browser Rendering + upload to R2

## HTML vs `htmlx`

Use `.html` templates.

- `.html` is the web standard and works with all tooling
- `htmlx` is not a standard HTML template format
- if you mean `htmx`, it still uses normal `.html` files

## Project Layout

- `config/pipeline.config.yaml`: single control plane for styles, archetypes, fonts, formats, limits, templates, and feature flags
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

## API Routes

- `GET /health`
- `GET /template/<format>` preview renderer (API key required)
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
- `image` (choose `auto|feature|stock|ai|custom`, plus `customUrl` and prompt controls)

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
