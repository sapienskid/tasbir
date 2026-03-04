# Troubleshooting

This guide covers common failures and how to fix them quickly.

## Build-Time Errors

### `Duplicate template id: ...`

Cause:

- two entries in `templates:` share same `id`

Fix:

- make all template IDs unique
- rerun `pnpm run build:templates`

### `Template <id> references unknown format/style/archetype`

Cause:

- typo or missing key in `formats`, `template_styles.styles`, or `post_archetypes.archetypes`

Fix:

- correct reference names
- ensure archetype/style/format exists before template entry

### `Format <name> points to missing default_template_id`

Cause:

- format default points to template ID not present in registry

Fix:

- set `formats.<name>.default_template_id` to valid template ID

### `Format <name> default_template_id does not support this format`

Cause:

- default template exists, but its `format`/`formats` constraints do not include the current format

Fix:

- add the format to `templates[].formats`, or remove format restriction for that template

## Runtime Errors

### `Missing env var GHOST_API_URL` or `GHOST_CONTENT_API_KEY`

Cause:

- required env vars not set

Fix:

- set values in `.dev.vars` (local) and Worker environment (deployed)

### `/template/*` returns 403

Cause:

- preview route disabled by `features.enable_template_preview`

Fix:

- set `features.enable_template_preview: true`
- run `pnpm run build:templates`

### Protected routes return 401

Cause:

- missing or invalid API key header

Fix:

- set `API_KEYS` in Worker env
- send `x-api-key: <key>` or `Authorization: Bearer <key>`

### `/webhook/ghost` returns 500 missing token

Cause:

- `GHOST_WEBHOOK_TOKEN` is not configured

Fix:

- set `GHOST_WEBHOOK_TOKEN` in local and deployed env

### `/generate-from-content` returns `title is required` or `content is required`

Cause:

- request body is missing required fields

Fix:

- provide both `title` and `content` (or `body`)

### Request returns 413

Cause:

- JSON payload exceeds configured `security.request_limits.max_json_body_bytes`

Fix:

- reduce payload size or raise limit in config and rebuild assets

### Request returns 429

Cause:

- route exceeded configured `security.rate_limit.max_requests_per_window`

Fix:

- throttle caller retries, or tune `security.rate_limit` for your traffic profile

### Ghost fetch errors

Symptoms:

- 404 for slug not found
- non-200 API response with Ghost details

Fix:

- verify `slug` exists in Ghost
- verify `GHOST_API_URL` and `GHOST_CONTENT_API_KEY`
- verify Content API endpoint includes `/ghost/api/content`

## Rendering and Style Issues

### Template not selected as expected

Check in order:

1. request `templateIds` override
2. request/model style and archetype values
3. template `archetypes` restrictions
4. format `default_template_id`

Debug tip:

- preview with explicit `templateId` first
- inspect output HTML data attributes (`data-template-id`, `data-template-style`, `data-template-archetype`)

### Slots are empty

Cause:

- slot key mismatch or no fallback for that slot

Fix:

- ensure template uses `{{SLOT:key}}` with key present in `slot_schema.defaults` or request/model slot data
- use preview query like `slot.key=value` to verify quickly

### Font not changing

Cause:

- invalid `fontProfile` ID or style/archetype map points to unknown profile

Fix:

- ensure profile exists in `typography.profiles`
- verify mapping values in `typography.selection`

### Colors look wrong

Cause:

- invalid hex values or unexpected token overrides

Fix:

- use full hex color form `#RRGGBB`
- test without token overrides to isolate issue

## Image Source Issues

### Stock image fallback never used

Cause:

- `features.enable_stock_image_search` disabled, missing `PEXELS_API_KEY`, or topic keyword check not matching

Fix:

- enable flag
- set `PEXELS_API_KEY`
- review `generation.stock_topic_keywords`

### AI image generation not used

Cause:

- `features.enable_ai_image_generation` disabled or model call failure

Fix:

- enable flag
- verify `AI` binding and model access

### Only feature image is used

Cause:

- `features.prefer_feature_image` true and model returns `use_feature_image: true`

Fix:

- set `prefer_feature_image: false` if you want stock/AI to be preferred

## Storage and URL Issues

### `url` fields are `null`

Cause:

- `R2_PUBLIC_BASE_URL` not configured

Fix:

- set `R2_PUBLIC_BASE_URL` to your public R2 domain

### Unexpected R2 key paths

Cause:

- storage mode or prefix overrides in request/env

Fix:

- verify request `storage` options
- verify `R2_KEY_PREFIX`
- verify `config.storage` defaults

## Quick Recovery Checklist

1. run `pnpm run build:assets`
2. run `pnpm run check`
3. run `pnpm run test`
4. test `GET /health`
5. test `GET /template/<format>` with explicit `templateId`
6. test `POST /generate-from-content` with minimal payload
