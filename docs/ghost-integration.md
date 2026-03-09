# Ghost Integration Guide

Connect Ghost to this Worker for automatic social asset generation on publish/edit events.

## 1. Prerequisites

- A running Ghost site with admin access
- This Worker deployed and reachable at a public URL
- `POST /webhook/ghost` route enabled (default)

## 2. Worker Env Setup

Set these environment variables in Worker runtime:

- `GHOST_API_URL` (example: `https://blog.example.com/ghost/api/content`)
- `GHOST_CONTENT_API_KEY`
- `GHOST_WEBHOOK_SECRET` (recommended)

Optional legacy/manual mode:

- `GHOST_WEBHOOK_TOKEN`

For direct Ghost integration, keep `security.api_auth.require_for_webhook: false` (default), because Ghost does not send your Worker API key header.

## 3. Create Ghost Custom Integration

In Ghost Admin:

1. Go to `Settings` -> `Integrations`
2. Create a Custom Integration
3. Copy the integration Content API key into Worker env as `GHOST_CONTENT_API_KEY`

Use your Ghost domain for `GHOST_API_URL`:

- `https://<your-ghost-domain>/ghost/api/content`

## 4. Configure Ghost Webhook

In the same Ghost integration:

1. Add webhook endpoint:
- `https://<your-worker-domain>/webhook/ghost`
2. Choose event(s):
- `post.published`
- optional: `post.published.edited`
3. Set webhook secret:
- must match Worker `GHOST_WEBHOOK_SECRET`

Worker verifies Ghost signature header:

- `x-ghost-signature: sha256=<digest>, t=<timestamp>`

## 5. How Triggering Works

1. Ghost sends webhook JSON payload to `/webhook/ghost`
2. Worker verifies signature
3. Worker resolves slug from payload (`post.current.slug`, fallbacks supported)
4. Worker fetches post data from Ghost Content API
5. Worker runs generation and stores assets in R2

## 6. Validate End-to-End

Publish a post in Ghost, then check Worker logs.

Expected behavior:

- `POST /webhook/ghost` returns `200`
- response contains `ok: true` and slug
- assets are written to R2 under your configured prefix

## 7. Legacy Token Mode (Optional)

If you call `/webhook/ghost` from a custom sender (not Ghost-native signing), send:

- `x-webhook-token: <GHOST_WEBHOOK_TOKEN>`

Ghost-native signed mode is recommended for production.

## 8. Common Pitfalls

- `401 Unauthorized webhook signature`:
- webhook secret mismatch between Ghost and Worker
- malformed `x-ghost-signature` header
- `500 Missing env var GHOST_WEBHOOK_SECRET`:
- set webhook secret in Worker env
- `400 Could not resolve slug`:
- webhook payload missing supported slug/url fields

## References

- https://docs.ghost.org/webhooks
- https://docs.ghost.org/admin-api/webhooks/creating-a-webhook
- https://developers.cloudflare.com/workers/runtime-apis/handlers/fetch/
- https://github.com/TryGhost/Ghost/blob/main/ghost/core/core/server/services/webhooks/webhook-trigger.js
