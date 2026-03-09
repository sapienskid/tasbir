# Deployment

Production deployment workflow for the Cloudflare Worker runtime.

## 1. Validate Before Deploy

```bash
pnpm run build
pnpm run test
pnpm exec wrangler deploy --env staging --dry-run
```

`wrangler deploy --dry-run` builds the Worker bundle without publishing.

## 2. Configure Environment Secrets

Set secrets per environment (staging and production):

```bash
wrangler secret put API_KEYS --env staging
wrangler secret put API_KEYS --env production

wrangler secret put GHOST_API_URL --env staging
wrangler secret put GHOST_CONTENT_API_KEY --env staging
wrangler secret put GHOST_WEBHOOK_SECRET --env staging
# Optional legacy mode:
# wrangler secret put GHOST_WEBHOOK_TOKEN --env staging

wrangler secret put GHOST_API_URL --env production
wrangler secret put GHOST_CONTENT_API_KEY --env production
wrangler secret put GHOST_WEBHOOK_SECRET --env production
# Optional legacy mode:
# wrangler secret put GHOST_WEBHOOK_TOKEN --env production
```

Optional secrets/vars should also be configured if used:
- `NOTIFY_WEBHOOK_URL`
- `R2_PUBLIC_BASE_URL`
- `BRAND_NAME`
- `LLM_MODEL`
- `IMAGE_MODEL`

## 3. Check `wrangler.jsonc` Environment Profiles

`wrangler.jsonc` includes:
- base config
- `env.staging`
- `env.production`

Each env can override:
- `name`
- `r2_buckets`
- `vars`

Use one R2 binding (`OUTPUT_BUCKET`) per env profile. If you use separate staging/production buckets, only change the `bucket_name` for that binding.

If Ghost will call `/webhook/ghost` directly in production, keep `security.api_auth.require_for_webhook: false` unless you front Ghost with a relay that adds API auth headers.

## 4. Deploy

Staging:

```bash
pnpm exec wrangler deploy --env staging
```

Production:

```bash
pnpm run deploy
```

`pnpm run deploy` maps to `wrangler deploy --env production`.

## 5. Verify

Health check:

```bash
curl https://<your-worker-domain>/health
```

Template preview check:

```bash
curl "https://<your-worker-domain>/template/instagram-square?templateId=layout/statement-cta&title=Deploy%20Check&caption=Template%20route%20ok" -H "x-api-key: <api-key>"
```

## 6. Observe

```bash
pnpm exec wrangler tail --env staging
pnpm exec wrangler tail --env production
```

Use tailing after deploys to confirm request volume, errors, and latency patterns.
