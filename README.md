# Tasbir

A Cloudflare Worker-based social media asset pipeline that turns source content into multi-platform social outputs — powered by AI, driven by settings, and templated for consistency.

## Features

- **Settings-driven**: Configure brand voice, campaign goals, formats, and templates once through the UI. Every API call uses these settings automatically.
- **Custom HTML templates**: Create simple HTML templates with `{{slot}}` placeholders. AI auto-selects the right template based on content type.
- **AI-powered**: Content classification, template matching, and full HTML generation when no template fits.
- **Multi-platform**: Instagram, Twitter/X, LinkedIn, and custom formats.
- **Design tokens**: AI-generated or custom design systems with full color, typography, and component control.
- **Headless API**: Simple API — just send content, get posts back. All configuration is managed through the UI.

## Quick Start

```bash
pnpm install
cp .dev.vars.example .dev.vars
# Configure your env vars
pnpm run dev
```

## API

### Generate Posts (Simple)

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Ship Better Content Systems",
    "content": "Turn one long article into platform-native assets..."
  }'
```

That's it. All configuration (brand, formats, templates, campaign goals) is loaded from your saved settings.

### Manage Settings

```bash
# Get current settings
curl http://127.0.0.1:8787/settings -H 'x-api-key: your-api-key'

# Update settings
curl -X PATCH http://127.0.0.1:8787/settings \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "brand": { "name": "My Brand", "tone": "confident" },
    "formats": { "enabled": ["instagram-square", "twitter-card"] }
  }'
```

### Manage Templates

```bash
# List templates
curl http://127.0.0.1:8787/templates -H 'x-api-key: your-api-key'

# Create template
curl -X PUT http://127.0.0.1:8787/templates/quote-card \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "html": "<!DOCTYPE html><html><body><h1>{{headline}}</h1><p>{{quote}}</p></body></html>",
    "name": "Quote Card",
    "category": "quote"
  }'

# Delete template
curl -X DELETE http://127.0.0.1:8787/templates/quote-card -H 'x-api-key: your-api-key'
```

### Health Check

```bash
curl http://127.0.0.1:8787/health
```

Returns dependency status (R2, KV namespaces).

## Architecture

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Content   │────>│   Pipeline   │────>│   Assets    │
│   (Ghost /  │     │   (AI +      │     │   (R2 PNG)  │
│    Direct)  │     │   Templates) │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Settings   │
                    │  (KV)       │
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Templates  │
                    │  (KV + R2)  │
                    └─────────────┘
```

## Resource Usage

|Resource|Purpose|
|---|---|
|**KV**|Settings, template metadata|
|**R2**|Template HTML files, rendered PNG assets|
|**Durable Objects**|Marketing orchestrator agent|
|**AI**|Content classification, HTML generation, design tokens|
|**Browser Rendering**|HTML to PNG screenshot|

## Deployment

Single deploy model: the Cloudflare Worker serves both the API and the dashboard UI from one URL.

```bash
pnpm run validate
pnpm run deploy:staging
pnpm run deploy:production
```

Make sure KV namespaces are created and configured in `wrangler.jsonc` for your environment.

## Production Readiness

This repository intentionally does not include a GitHub Actions deployment workflow.
Run validation and deployment commands manually (or from your own CI/CD system).

### 1. Validate Before Every Deploy

```bash
pnpm run validate
```

This runs worker typecheck/tests and dashboard build/lint.

### 2. Configure Required Secrets

Set Worker secrets per environment (example for production):

```bash
wrangler secret put API_KEYS --env production
wrangler secret put GOOGLE_API_KEY --env production
wrangler secret put GHOST_CONTENT_API_KEY --env production
wrangler secret put GHOST_WEBHOOK_TOKEN --env production
wrangler secret put GHOST_WEBHOOK_SECRET --env production
```

Optional (if not using Workers AI binding directly):

```bash
wrangler secret put CLOUDFLARE_API_TOKEN --env production
wrangler secret put CLOUDFLARE_ACCOUNT_ID --env production
```

### 3. Configure Public Vars

`wrangler.jsonc` already includes production defaults for:

- `API_AUTH_REQUIRE_FOR_PREVIEW=true`
- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_WINDOW_SECONDS=60`
- `RATE_LIMIT_MAX_REQUESTS_PER_WINDOW=120`
- `ALLOW_PRIVATE_NETWORK_TARGETS=false`

You can override CORS and host allowlists with env vars from `.dev.vars.example`.

### 4. Deploy (UI + API Together)

```bash
pnpm run deploy:staging
pnpm run deploy:production
```

This builds `ui/dist` and deploys one Worker that serves:

- API routes (for example `/generate-from-content`, `/settings`, `/templates`)
- UI/static assets and SPA routes from the same domain

### 5. UI Runtime Config

For all-in-one deployment, keep the UI API base empty (same-origin calls).

Set `ui/.env.production`:

```bash
VITE_API_BASE=""
VITE_API_KEY="<same-api-key-used-by-worker>"
```

### 6. Smoke Test Production

```bash
curl https://social-post-pipeline.<subdomain>.workers.dev/
curl https://social-post-pipeline.<subdomain>.workers.dev/health
curl -X POST https://social-post-pipeline.<subdomain>.workers.dev/generate-from-content \
  -H 'x-api-key: <api-key>' \
  -H 'content-type: application/json' \
  -d '{"title":"Production check","content":"Smoke test content"}'
```
