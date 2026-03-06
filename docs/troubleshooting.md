# Troubleshooting

Common issues and fast fixes.

## Build-Time Errors

### `Duplicate template id: ...`

Cause:

- two template files declare the same `@id`

Fix:

- make IDs unique
- rerun `pnpm run build:templates`

### `Template <id> references unknown format`

Cause:

- template `format`/`formats` contains unsupported format key

Fix:

- use one of: `instagram-portrait`, `instagram-square`, `instagram-story`, `carousel-post`, `twitter-card`, `linkedin-post`

### `Format <name> points to missing default_template_id`

Cause:

- `formats.<name>.default_template_id` does not exist in template registry

Fix:

- set it to a valid template ID

### `Format <name> default_template_id does not support this format`

Cause:

- default template is format-restricted and does not include that format

Fix:

- add format to `templates[].formats` or change default template

### Missing system shell error

Cause:

- required system templates are missing:
- `templates/system/head-shell.html`
- `templates/system/frame-shell.html`

Fix:

- restore missing file(s)
- rerun build

## Auth and Security Errors

### 401 on protected routes

Cause:

- missing/invalid API key

Fix:

- set `API_KEYS`
- send `x-api-key` or Bearer token

### 403 on `/template/*`

Cause:

- `features.enable_template_preview` is disabled

Fix:

- set it to `true` and rebuild assets

### 429 responses

Cause:

- rate limit exceeded (`security.rate_limit`)

Fix:

- throttle caller
- tune rate limit config for expected traffic

### 413 responses

Cause:

- request body exceeds `security.request_limits.max_json_body_bytes`

Fix:

- reduce payload size or increase limit

## Input/Validation Errors

### `/generate` says slug/url required

Cause:

- request body has neither `slug` nor `url`

Fix:

- provide one of them

### `/generate-from-content` says title/content required

Cause:

- missing required direct-content fields

Fix:

- provide `title` and one of `content`/`body`

### `templateIds.<format> references unknown template`

Cause:

- template ID not available for that format

Fix:

- check `/template-catalog`
- use valid template ID for target format

## Template/Rendering Issues

### Wrong template selected

Check in order:

1. request `templateIds` override
2. LLM planner output
3. format default template

Debug steps:

- call `/template-catalog`
- preview with explicit `templateId`
- verify selected IDs in response `template_plan.template_ids`

### Slots look empty

Cause:

- slot key mismatch between template and payload

Fix:

- verify template uses `{{SLOT:key}}`
- verify keys in `slotOverrides`/LLM output match normalized slot names
- test with preview query `slot.key=value`

### Preview HTML renders but looks unstyled

Cause:

- stale generated assets or CSS not rebuilt

Fix:

- run `pnpm run build:assets`
- restart dev server

### Unexpected colors/contrast

Cause:

- invalid token override values or extreme brand/input colors

Fix:

- use valid hex colors (`#RRGGBB`)
- retest without token overrides

## Image Issues

### AI image generation not used

Cause:

- feature disabled or model invocation fails

Fix:

- enable `features.enable_ai_image_generation`
- verify `AI` binding and model availability

### Always using feature image

Cause:

- feature image preferred and available

Fix:

- set `features.prefer_feature_image: false`
- or use explicit request `image.mode`

## Storage and URL Issues

### Asset `url` fields are `null`

Cause:

- `R2_PUBLIC_BASE_URL` is not set

Fix:

- configure public base URL for bucket

### Unexpected R2 keys

Cause:

- `storage` overrides or env prefix overrides

Fix:

- inspect request `storage`
- inspect `R2_KEY_PREFIX`
- inspect `config.storage`

## Fast Recovery Checklist

1. `pnpm run build:assets`
2. `pnpm run check`
3. `pnpm run test`
4. `GET /health`
5. `GET /template-catalog`
6. preview one template with explicit `templateId`
7. run minimal `POST /generate-from-content`
