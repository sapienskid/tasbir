# Getting Started

This guide gets you from clone to first generated assets with minimum guesswork.

## 1. Install Requirements

- Node.js 20+
- pnpm 9+
- Cloudflare account
- Workers AI access
- Browser Rendering enabled
- an R2 bucket

Install dependencies:

```bash
pnpm install
```

## 2. Verify Wrangler Bindings

Check `wrangler.jsonc` has these bindings:

- `ai.binding = "AI"`
- `browser.binding = "BROWSER"`
- `r2_buckets` includes `binding = "OUTPUT_BUCKET"`

If you change bucket names or bindings, keep names consistent with `src/index.ts`.

## 3. Configure Environment Variables

Create local env file:

```bash
cp .dev.vars.example .dev.vars
```

Required values:

- `GHOST_API_URL`
- `GHOST_CONTENT_API_KEY`
- `API_KEYS` (comma-separated accepted API keys)

Optional but common:

- `R2_PUBLIC_BASE_URL` for public URLs in API response
- `PEXELS_API_KEY` for stock-photo fallback
- `GHOST_WEBHOOK_TOKEN` (required for `/webhook/ghost`)
- `NOTIFY_WEBHOOK_URL` for completion callbacks
- `NOTIFY_HOST_ALLOWLIST` to restrict callback hosts
- `IMAGE_HOST_ALLOWLIST` to restrict external image hosts

## 4. Build Generated Assets

This project compiles config and templates into runtime files.

Run before local dev, and after any template/config/style changes:

```bash
pnpm run build:assets
```

What this does:

- builds Tailwind CSS into `src/styles/tailwind-css.ts`
- validates `config/pipeline.config.yaml`
- embeds all template HTML into `src/generated/template-assets.ts`

## 5. Run Locally

```bash
pnpm run dev
```

Health check:

```bash
curl http://127.0.0.1:8787/health
```

Expected response:

```json
{
  "ok": true
}
```

## 6. Preview a Template in Browser

Quick visual check without running full generation:

```bash
curl "http://127.0.0.1:8787/template/instagram-post?templateStyle=data&archetype=metric&slot.metric_value=84%25&slot.metric_label=Retention&slot.headline=Signal%20over%20noise" \
  -H "x-api-key: your-api-key"
```

You can pass:

- `templateStyle`, `templateId`, `archetype` / `templateArchetype`
- `fontProfile`
- `slot.<name>=...` values
- design controls like `preset`, `textAlign`, `imageOpacity`

## 7. Generate From Direct Content

Use this while developing, so Ghost is not required in every test run:

```bash
curl -X POST http://127.0.0.1:8787/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Build a Repeatable Content Engine",
    "content": "Use one source article to generate multi-platform assets with consistent design and copy.",
    "templateStyle": "minimal",
    "postArchetype": "checklist",
    "slotOverrides": {
      "headline": "Build a repeatable engine",
      "step_1": "Extract key ideas",
      "step_2": "Map by platform",
      "step_3": "Render and review",
      "step_4": "Publish and measure"
    }
  }'
```

## 8. Generate From Ghost Slug

```bash
curl -X POST http://127.0.0.1:8787/generate \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{"slug":"your-post-slug"}'
```

## 9. Understand Output Paths

By default, assets are written to:

- `social-assets/<slug>/instagram-post.png`
- `social-assets/<slug>/instagram-story.png`
- `social-assets/<slug>/twitter-card.png`
- `social-assets/<slug>/linkedin-post.png`
- `social-assets/<slug>/carousel-slide-1.png` ...

Storage behavior can be changed with request-level `storage` or `config.storage`.

Use request-level `output.formats` to generate only selected formats, for example `["twitter-card"]`.

## 10. Common Edit Workflows

Change brand defaults:

- edit `brand.default_name` and `brand.default_color` in `config/pipeline.config.yaml`
- run `pnpm run build:assets`

Add new template:

1. create a new `.html` file under `templates/<format>/`
2. add a template record under `templates:` in YAML
3. run `pnpm run build:templates`
4. preview via `GET /template/<format>?templateId=<new-id>`

Tune AI behavior:

- update `generation.llm.system_prompt`
- update `generation.llm.user_instructions`
- adjust `generation.limits`

## 11. Validate Before Commit

```bash
pnpm run build:assets
pnpm run check
pnpm run test
```

## Next Docs

- [Template System](template-system.md)
- [Config Reference](config-reference.md)
- [API Reference](api-reference.md)
- [Troubleshooting](troubleshooting.md)
