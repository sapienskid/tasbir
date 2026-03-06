# Getting Started

This guide takes you from clone to first generated assets.

## 1. Requirements

- Node.js 20+
- pnpm 9+
- Cloudflare account with:
- Workers AI
- Browser Rendering
- R2 bucket

Install deps:

```bash
pnpm install
```

## 2. Configure Wrangler Bindings

Check `wrangler.jsonc` contains bindings used by runtime:

- `AI`
- `BROWSER`
- `OUTPUT_BUCKET`

Keep binding names aligned with `src/index.ts`.

## 3. Configure Environment Variables

Create local env file:

```bash
cp .dev.vars.example .dev.vars
```

Required for all protected routes:

- `API_KEYS`

Required for Ghost-backed flow (`/generate`, `/webhook/ghost`):

- `GHOST_API_URL`
- `GHOST_CONTENT_API_KEY`
- `GHOST_WEBHOOK_TOKEN` (webhook route)

Common optional values:

- `R2_PUBLIC_BASE_URL`
- `DEFAULT_BRAND_COLOR`
- `BRAND_NAME`
- `LLM_MODEL`
- `IMAGE_MODEL`

## 4. Build Generated Runtime Assets

Run after any change in:

- `config/pipeline/*.yaml`
- `templates/**/*.html`
- `src/styles/template.css`

Command:

```bash
pnpm run build:assets
```

This regenerates `src/generated/template-assets.json`.

## 5. Run Locally

```bash
pnpm run dev:design
```

Health check:

```bash
curl http://127.0.0.1:8787/health
```

## 6. Preview a Template

Direct template request example:

```bash
curl "http://127.0.0.1:8787/template/instagram-square?templateId=layout/statement-cta&slot.headline=Launch%20Week&slot.supporting_line=One%20guide%2C%20all%20platforms&slot.cta_text=Read%20Now" \
  -H 'x-api-key: your-api-key'
```

Preview is useful for verifying layout and slot behavior without full generation.

## 7. Generate From Direct Content

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Build a Repeatable Content Engine",
    "content": "Use one source article to generate platform-ready social assets.",
    "prompt": "Practical tone, no buzzwords.",
    "output": {
      "formats": ["instagram-square", "twitter-card", "linkedin-post"],
      "postCount": 2
    }
  }'
```

Campaign-planned request (preferred):

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Build a Repeatable Content Engine",
    "content": "Use one source article to generate platform-ready social assets.",
    "campaign": {
      "platforms": ["instagram-square", "twitter-card", "linkedin-post"],
      "counts": {
        "instagram-square": 2,
        "twitter-card": 2,
        "linkedin-post": 1
      }
    },
    "image": {
      "mode": "none"
    }
  }'
```

## 8. Generate From Ghost

```bash
curl -X POST http://127.0.0.1:8787/generate \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{"slug":"your-post-slug"}'
```

You can also pass `url` instead of `slug`.

## 9. Add a New Template

1. Create HTML file in `templates/`.
2. Optional: declare `@formats: twitter-card,linkedin-post` in front-matter.
3. Run:

```bash
pnpm run build:templates
```

4. Verify:

- `GET /template/<format>?templateId=<new-id>`

## 10. Validate Before Commit

```bash
pnpm run build:assets
pnpm run check
pnpm run test
```

## Next Docs

- [Architecture](architecture.md)
- [Template System](template-system.md)
- [Configuration Reference](config-reference.md)
- [API Reference](api-reference.md)
- [Troubleshooting](troubleshooting.md)
- [Deployment](deployment.md)
