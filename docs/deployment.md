# Deployment

Production deployment workflow for the Cloudflare Worker runtime.

## 1. Validate Before Deploy

```bash
pnpm run build:assets
pnpm run check
pnpm run test
pnpm run deploy:dry-run
```

`deploy:dry-run` builds the Worker bundle without publishing.

## 2. Configure Environment Secrets

Set secrets per environment (staging and production):

```bash
wrangler secret put API_KEYS --env staging
wrangler secret put API_KEYS --env production

wrangler secret put GHOST_API_URL --env staging
wrangler secret put GHOST_CONTENT_API_KEY --env staging
wrangler secret put GHOST_WEBHOOK_TOKEN --env staging

wrangler secret put GHOST_API_URL --env production
wrangler secret put GHOST_CONTENT_API_KEY --env production
wrangler secret put GHOST_WEBHOOK_TOKEN --env production
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

If you use separate staging/production buckets, update `r2_buckets` in each env profile.

## 4. Deploy

Staging:

```bash
pnpm run deploy:staging
```

Production:

```bash
pnpm run deploy:production
```

Default `pnpm run deploy` maps to production.

## 5. Verify

Health check:

```bash
curl https://<your-worker-domain>/health
```

Template catalog check:

```bash
curl "https://<your-worker-domain>/template-catalog" -H "x-api-key: <api-key>"
```

## 6. Observe

```bash
pnpm run tail:staging
pnpm run tail:production
```

Use tailing after deploys to confirm request volume, errors, and latency patterns.
