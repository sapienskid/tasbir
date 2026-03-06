# Social Media Asset Pipeline Worker

A Cloudflare Worker that turns source content into multi-platform social outputs:

- captions
- rendered PNG assets
- template slot content
- optional generated variants (`output.postCount`)

Supported output formats:

- `instagram-portrait` (1080x1350)
- `instagram-square` (1080x1080)
- `instagram-story` (1080x1920)
- `carousel-post` (1080x1350)
- `twitter-card` (1200x630)
- `linkedin-post` (1200x627)

## Core Model

This project is template-driven and CSS-token-driven:

- templates are structural skeletons in `templates/*.html`
- shared wrapper fragments are in `templates/system/*.html`
- utility-first styles are authored in `src/styles/template.css` and compiled to `src/generated/template.css`
- runtime assets are compiled into `src/generated/template-assets.json`

No runtime style CDN/script injection, no style/archetype/font-profile matrix.

## High-Level Flow

1. Input arrives from:
- `POST /generate` (Ghost slug/url)
- `POST /generate-from-content` (direct content)
- `POST /webhook/ghost`
2. Worker builds template candidates from discovered `templates/*.html` files.
3. LLM chooses template IDs per requested format (unless forced via `templateIds`).
4. Required slot keys are extracted from selected template `{{SLOT:key}}` placeholders.
5. LLM generates structured output (captions, slides, hashtags, image prompt, slot content).
6. Worker resolves image source (feature/stock/AI/custom/none).
7. HTML is rendered and screenshotted via Cloudflare Browser Rendering.
8. PNG files are stored in R2 and returned in API response.

## Project Layout

- `config/pipeline.config.yaml`: composed config entrypoint (`extends`)
- `config/pipeline/templates.yaml`: brand, format, and preview defaults
- `config/pipeline/content.yaml`: generation prompts/limits/fallbacks
- `config/pipeline/runtime.yaml`: runtime, features, security, storage
- `templates/*.html`: format-agnostic content skeletons
- `templates/system/*.html`: shared wrappers (`head-shell`, `frame-shell`, partials)
- `src/styles/template.css`: Tailwind theme tokens + utility source
- `scripts/embed-template-assets.mjs`: build-time embed + validation
- `src/generated/template-assets.json`: generated runtime bundle
- `src/generated/template-assets.ts`: typed wrapper over generated JSON
- `src/index.ts`: API routes + orchestration pipeline
- `src/ai.ts`: structured generation + template assignment planner
- `src/templates.ts`: template slot extraction/interpolation + render assembly
- `src/template-theme.ts`: token derivation and render-time controls

## Prerequisites

- Node.js 20+
- pnpm 9+
- Cloudflare account with:
- Workers AI
- Browser Rendering
- R2
- Ghost Content API key (only required for `/generate` and webhook flow)

## Quick Start

1. Install:

```bash
pnpm install
```

2. Configure env:

```bash
cp .dev.vars.example .dev.vars
```

3. Build runtime assets:

```bash
pnpm run build:assets
```

4. Run locally (fully local runtime + live reload):

```bash
pnpm run dev
```

5. Optional remote dev mode (Cloudflare edge runtime):

```bash
pnpm run dev:remote
```

6. Check health:

```bash
curl http://127.0.0.1:8787/health
```

## First End-to-End Request (Direct Content)

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Ship Better Content Systems",
    "content": "Turn one long article into platform-native assets with a reusable template pipeline.",
    "prompt": "Practical, confident tone for solo founders.",
    "output": {
      "formats": ["instagram-square", "twitter-card", "linkedin-post"],
      "postCount": 2
    }
  }'
```

Campaign-planned generation (preferred):

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Ship Better Content Systems",
    "content": "Turn one long article into platform-native assets with a reusable template pipeline.",
    "campaign": {
      "platforms": ["instagram-square", "twitter-card", "linkedin-post"],
      "counts": {
        "instagram-square": 2,
        "twitter-card": 3,
        "linkedin-post": 1
      }
    },
    "image": {
      "mode": "none"
    }
  }'
```

## Template Preview

Render preview HTML without running full generation.

Local browser workflow (template-only, no deploy dependency):

```bash
pnpm run dev:design
```

Then open one of the local review pages:

```text
http://127.0.0.1:8787/preview
http://127.0.0.1:8787/preview/gallery
```

Or open a direct template URL:

```text
http://127.0.0.1:8787/template/instagram-square?templateId=layout/single-metric-focus&slot.metric_value=9.8K&slot.metric_label=Engagement&slot.headline=Signal%20that%20compounds&slot.insight_line=One%20metric%20needs%20context
```

`dev:design`/`dev:templates` watches template/style/config files, rebuilds assets on save, and uses Wrangler local live-reload so the browser refreshes automatically. It also sets `API_AUTH_REQUIRE_FOR_PREVIEW=false` for this local session so preview URLs open directly in browser.

Direct API request example (when preview auth is enabled):

```bash
curl "http://127.0.0.1:8787/template/instagram-square?templateId=layout/single-metric-focus&slot.metric_value=9.8K&slot.metric_label=Engagement&slot.headline=Signal%20that%20compounds&slot.insight_line=One%20metric%20needs%20context" \
  -H 'x-api-key: your-api-key'
```

Useful preview query params:

- core: `title`, `caption`, `imageUrl`, `brandingColor`, `brand`/`brandName`, `templateId`
- carousel: `heading`, `body`, `slide`, `total`
- slots: `slot.<key>=value` or `slot_<key>=value`
- design controls: `showBrandBadge`, `showSlideBadge`, `showMetaFooter`, `showTitleKicker`, `showDecorLayers`, `textAlign`, `imageOpacity`, `contentMaxWidth`, `contentInset`, `metaLeftText`, `metaRightText`
- token overrides: `tokenPrimaryText`, `tokenSecondaryText`, `tokenMutedText`, `tokenSurfaceBase`, `tokenSurfaceElevated`, `tokenBorderSubtle`, `tokenAccent`, `tokenAccentForeground`

If you run plain `pnpm run dev` and still want browser-openable template previews, set:
- `API_AUTH_REQUIRE_FOR_PREVIEW=false` in `.dev.vars`

## Template Catalog

```bash
curl "http://127.0.0.1:8787/template-catalog" -H 'x-api-key: your-api-key'
```

Catalog includes:

- formats and dimensions
- templates and versions
- templates mapped by format

## How New Templates Are Recognized

1. Add a new file under `templates/`.
2. Optional: add `@formats: format-a,format-b` in template front-matter to constrain compatibility.
3. Run `pnpm run build:templates`.
4. New template appears in `/template-catalog` and planner candidates automatically.

No TypeScript template registration is required.

## API Routes

- `GET /health`
- `GET /template/<format>`
- `GET /preview`
- `GET /preview/gallery`
- `GET /preview/screenshot?format=...&templateId=...`
- `GET /template-catalog`
- `POST /generate`
- `POST /generate-from-content`
- `POST /webhook/ghost`

## Deployment

Dry-run bundle check:

```bash
pnpm run deploy:dry-run
```

Deploy staging:

```bash
pnpm run deploy:staging
```

Deploy production:

```bash
pnpm run deploy:production
```

Tail logs:

```bash
pnpm run tail:staging
pnpm run tail:production
```

## Auth

Protected routes accept either:

- `x-api-key: <API_KEYS entry>`
- `Authorization: Bearer <API_KEYS entry>`

## Daily Commands

```bash
pnpm run build:assets
pnpm run check
pnpm run test
```

## Environment Variables

Required:

- `API_KEYS`
- `GHOST_API_URL` and `GHOST_CONTENT_API_KEY` (for Ghost-backed generation)
- `GHOST_WEBHOOK_TOKEN` (for webhook route)

Common optional:

- `R2_PUBLIC_BASE_URL`
- `PEXELS_API_KEY`
- `DEFAULT_BRAND_COLOR`
- `BRAND_NAME`
- `LLM_MODEL`
- `IMAGE_MODEL`
- `R2_KEY_PREFIX`
- `NOTIFY_WEBHOOK_URL`
- `NOTIFY_HOST_ALLOWLIST`
- `IMAGE_HOST_ALLOWLIST`
- `ALLOW_PRIVATE_NETWORK_TARGETS`
- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOWED_HEADERS`
- `CORS_ALLOW_CREDENTIALS`
- `CORS_MAX_AGE_SECONDS`

See `.dev.vars.example` for complete local example values.

## Documentation

- [Getting Started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Template System](docs/template-system.md)
- [Configuration Reference](docs/config-reference.md)
- [API Reference](docs/api-reference.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Design Principles](docs/design-principles.md)
- [Deployment](docs/deployment.md)
- [Research Summary](docs/research-summary.md)
