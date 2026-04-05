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

```
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

| Resource | Purpose |
|----------|---------|
| **KV** | Settings, template metadata |
| **R2** | Template HTML files, rendered PNG assets |
| **Durable Objects** | Marketing orchestrator agent |
| **AI** | Content classification, HTML generation, design tokens |
| **Browser Rendering** | HTML to PNG screenshot |

## Deployment

```bash
pnpm run deploy
```

Make sure KV namespaces are created and configured in `wrangler.jsonc` for your environment.
