# Tasbir

A Cloudflare Worker-based social media asset pipeline that turns source content into multi-platform social outputs — powered by AI, driven by settings, and templated for consistency.

## Features

- **Settings-driven**: Configure brand voice, campaign goals, formats, and templates once through the UI. Every API call uses these settings automatically.
- **AI-powered**: Content classification, template matching, full HTML generation, AI image generation, and carousel posts.
- **Multi-platform**: Instagram, Twitter/X, LinkedIn, Facebook, Pinterest, and custom formats.
- **Carousel posts**: Auto-expands into intro, content, and CTA slides with consistent visual identity.
- **Design tokens**: AI-generated or custom design systems with full color, typography, spacing, and component control.
- **Inline editing**: Click any generated post to edit content via slot placeholders. Preview updates live. Edits persist to KV.
- **AI images**: Contextual background/hero images via Cloudflare Workers AI (FLUX). Falls back gracefully when orchestrator is unavailable.
- **Headless API**: Simple API — send content, get posts back. All configuration managed through the UI.
- **Figma plugin**: Generate social posts directly inside Figma as frames with image fills. Sync design tokens to Figma Variables.

## Quick Start

```bash
pnpm install
cp .dev.vars.example .dev.vars
# Edit .dev.vars with your GOOGLE_API_KEY and API_KEYS
pnpm run dev          # Terminal 1: starts the API worker on :8787
pnpm run dev:ui       # Terminal 2: starts the dashboard on :5173
```

Open `http://localhost:5173` for the dashboard. Configure API key in Settings tab.

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check (R2, KV status) |
| `GET` | `/openapi.json` | No | OpenAPI 3.1 spec |
| `GET` | `/config` | No | Full pipeline config |
| `GET` | `/config/design-tokens` | No | Default design tokens |
| `GET` | `/config/formats` | No | All output formats |
| `GET` | `/settings` | No | Get workspace settings |
| `PUT` | `/settings` | Yes | Replace settings |
| `PATCH` | `/settings` | Yes | Merge-patch settings |
| `GET` | `/tokens` | No | Get saved design tokens |
| `PUT` | `/tokens` | Yes | Save design tokens |
| `POST` | `/generate-tokens` | Yes | AI token generation from vibe text |
| `GET` | `/templates` | No | List HTML templates |
| `GET` | `/templates/:id` | No | Get template + HTML |
| `PUT` | `/templates/:id` | Yes | Create/update template |
| `DELETE` | `/templates/:id` | Yes | Delete template |
| `GET/PUT/DELETE` | `/formats` | Yes | CRUD custom format definitions |
| `POST` | `/generate-from-content` | Yes | Generate posts from direct content |
| `POST` | `/generate-from-content/stream` | Yes | Streaming generation with SSE |
| `POST` | `/render-html` | Yes | Re-render edited HTML to PNG |
| `GET` | `/edited-content` | No | Retrieve persisted edits by slug+format |
| `DELETE` | `/edited-content` | Yes | Clear persisted edits |
| `POST` | `/save-to-r2` | Yes | Save base64 PNG to R2 |
| `GET` | `/asset?key=...` | Yes | Fetch rendered PNG asset |

### Generate Posts

```bash
curl -X POST https://tasbir.example.com/generate-from-content \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "title": "Ship Better Content Systems",
    "content": "Turn one long article into platform-native assets...",
    "output": { "formats": ["instagram-square", "carousel-post"], "postCount": 1 },
    "image": { "mode": "ai" }
  }'
```

### Content Editing

```bash
# Edit a generated post and re-render
curl -X POST https://tasbir.example.com/render-html \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{
    "html": "<!DOCTYPE html>...<h1>{{headline}}</h1>...",
    "width": 1080, "height": 1080,
    "format": "instagram-square",
    "slug": "my-post",
    "slot_values": { "headline": "New Headline", "body": "Updated content" }
  }'

# Retrieve previously saved edits
curl "https://tasbir.example.com/edited-content?slug=my-post&format=instagram-square"
```

### Streaming

```bash
curl -X POST https://tasbir.example.com/generate-from-content/stream \
  -H 'x-api-key: your-api-key' \
  -H 'content-type: application/json' \
  -d '{"title": "...", "content": "..."}'
# Returns SSE events: start, classifying, generating (per format), rendering, complete
```

## Architecture

```text
┌─────────────┐     ┌───────────────────────────────────┐     ┌─────────────┐
│   Content   │────>│            Pipeline               │────>│   Assets    │
│   (Ghost /  │     │  Orchestrator → Classify → Image  │     │   (R2 PNG)  │
│    Direct)  │     │  → HTML Gen → Render → Assemble   │     │             │
└─────────────┘     └───────────────────────────────────┘     └─────────────┘
       │                        │         │
       ▼                        ▼         ▼
  ┌─────────┐           ┌──────────┐  ┌──────────┐
  │ Figma   │           │ Google   │  │ CF       │
  │ Plugin  │           │ Gemini   │  │ Browser  │
  └─────────┘           └──────────┘  │ Render   │
                                      └──────────┘
```

## Resource Usage

| Resource | Purpose |
|----------|---------|
| **KV** | Settings, template metadata, persisted edits |
| **R2** | Template HTML files, rendered PNG assets, design tokens |
| **Durable Objects** | Marketing orchestrator agent |
| **AI** | Content classification, HTML generation, design tokens, AI images (FLUX) |
| **Browser Rendering** | HTML to PNG screenshot via Puppeteer |

## Deployment

```bash
pnpm run typecheck
pnpm run test
pnpm run build        # builds the UI dashboard
pnpm run deploy       # wrangler deploy (runs build automatically)
```

### Required Secrets

```bash
wrangler secret put API_KEYS
wrangler secret put GOOGLE_API_KEY
wrangler secret put GHOST_API_URL           # optional
wrangler secret put GHOST_CONTENT_API_KEY   # optional
wrangler secret put GHOST_WEBHOOK_SECRET    # optional
```

## Figma Plugin

Generate social posts directly inside Figma. The plugin is in `figma-plugin/`.

### Features
- Content form → generate posts → frames created with rendered PNG as image fills
- Edit & re-render: select a generated frame, edit content, update the image fill
- Design token → Figma Variables sync: one-click push of color tokens
- Template browsing
- Progress tracking during generation

### Development

```bash
cd figma-plugin
pnpm install
pnpm run build     # builds dist/code.js + dist/ui.html
```

Then in the Figma desktop app:
1. Plugins → Development → Import plugin from manifest
2. Select `figma-plugin/manifest.json`

**Note**: Figma plugin development requires the Figma desktop app (macOS/Windows). Linux users must publish the plugin to test via the browser.

### Submitting to Figma Community

1. **Prepare the plugin**
   ```bash
   cd figma-plugin
   pnpm run build
   # Verify dist/ contains: code.js, ui.html
   ```

2. **Create plugin listing**
   - Go to [Figma Community](https://www.figma.com/community) → your avatar → Plugins
   - Click "Create new plugin"
   - Set development link (optional): `https://tasbir.example.com`

3. **Upload bundle**
   - Zip the `dist/` directory: `zip -r tasbir-plugin.zip dist/`
   - Upload the zip in the plugin editor under "Build & Bundle"
   - Also zip and upload `manifest.json` if prompted separately

4. **Configure settings**
   - **Name**: "Tasbir — Social Post Generator"
   - **Description**: "Generate platform-optimized social media posts directly in Figma. Connect to your Tasbir API, input content, and get rendered frames with AI-powered designs, images, and editable content."
   - **Tags**: `social media`, `marketing`, `content`, `instagram`, `twitter`, `linkedin`
   - **Categories**: Content & publishing, Design tools
   - **Price**: Free or your choice

5. **Add screenshots** (required — 3+ images, 1920x960)
   - Settings/connection screen
   - Content form with generated frames on the Figma canvas
   - Token sync demonstration
   - Editing workflow

6. **Define network access**
   The plugin needs to reach your Tasbir API domain. In the submission form under "Network Access", or in the manifest:
   ```json
   "networkAccess": {
     "allowedDomains": ["none"],
     "devAllowedDomains": ["http://localhost:8787"],
     "reasoning": "Connects to the user's Tasbir API instance to generate social media post images from content."
   }
   ```
   Users configure their own API URL at runtime.

7. **Submit for review**
   - Click "Publish" → "Submit for review"
   - Figma review typically takes 2-4 weeks
   - Address any feedback from reviewers
   - Once approved, the plugin becomes available in the Figma Community
   - Users can install it directly from their Figma browser or desktop app

8. **Post-launch**
   - Users enter their Tasbir API base URL and API key in the plugin settings
   - The plugin makes requests to the configured API from the UI iframe (`null` origin)
   - Ensure your Tasbir API has CORS configured with `origin: "*"` (already the default)

### API Requirements for Plugin

The Tasbir API must:
- Be accessible over HTTPS (for production Figma plugins)
- Have CORS enabled with `Access-Control-Allow-Origin: *` (default)
- Accept the `x-api-key` header for authentication
- Expose `/generate-from-content`, `/render-html`, `/tokens`, `/templates`, `/settings`, `/health`

## License

MIT
