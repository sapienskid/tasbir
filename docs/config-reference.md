# Configuration Reference

Main config file:

- `config/pipeline.config.yaml`

This file is the control plane for the entire pipeline. Most behavior changes should be done here, not in `src/*.ts`.

## How Config Is Loaded

1. `scripts/embed-template-assets.mjs` reads YAML
2. script validates schema and template references
3. script writes generated runtime module: `src/generated/template-assets.ts`
4. Worker imports generated module at runtime

After config changes, run:

```bash
pnpm run build:templates
```

## Top-Level Sections

- `schema_version`
- `brand`
- `typography`
- `theming`
- `render`
- `runtime`
- `features`
- `security`
- `storage`
- `post_archetypes`
- `slot_schema`
- `generation`
- `template_styles`
- `formats`
- `preview_defaults`
- `templates`

## `schema_version`

Numeric schema version for config evolution.

```yaml
schema_version: 1
```

## `brand`

Default brand identity used when request/env does not override.

```yaml
brand:
  default_name: "Tasbir Blog"
  default_color: "#1f7a8c"
```

Runtime override precedence for brand name/color:

1. request payload (`brandName`, `brandingColor`)
2. env (`BRAND_NAME`, `DEFAULT_BRAND_COLOR`)
3. YAML defaults

## `typography`

Defines font profiles and auto-selection maps.

```yaml
typography:
  default_font_profile: editorial-serif
  profiles:
    editorial-serif:
      label: Editorial Serif
      llm_hint: Elegant and expressive...
      google_fonts_css2_query: "family=Fraunces..."
      display_font_css: '"Fraunces", serif'
      body_font_css: '"Plus Jakarta Sans", sans-serif'
  selection:
    by_style:
      data: data-mono
    by_archetype:
      metric: data-mono
```

Used for:

- preview route font loading
- generated assets font loading
- LLM schema enum for `font_profile`

## `theming`

Controls brand-token derivation and readability constraints.

Key areas:

- `readable_light_text`, `readable_dark_text`
- `color_engine` ratios and fallback colors
- contrast thresholds (`primary_text_min_contrast`, `secondary_text_min_contrast`, `muted_text_min_contrast`, `border_subtle_min_contrast`, `accent_foreground_min_contrast`)
- radius tokens (`radius.card`, `radius.pill`)

Use this section when you want global visual tone changes without editing templates.

## `render`

Controls layout and visual controls at render time.

### `control_defaults`

Global defaults:

- `showBrandBadge`
- `showSlideBadge`
- `showMetaFooter`
- `showTitleKicker`
- `textAlign`

### `format_control_defaults`

Per-format defaults:

- `default_preset`
- `contentMaxWidth`
- `contentInset`
- `textAlign`

### `preset_styles`

Named visual presets with gradient/overlay/shadow values.

These keys are consumed by `design.preset` overrides and preview `preset` query param.

### `caption_width_rules`

Per-format rules used to compute `{{CAPTION_MAX_WIDTH}}`.

### `meta_left_labels` / `meta_right_labels`

Default footer labels used when `showMetaFooter` is enabled.

### `frame_decor`

Shared frame styling:

- border alpha
- grain dot color/size
- grain background spacing

## `runtime`

Runtime behavior constants.

- `browser_keep_alive_ms`
- `page_set_content_wait_until`
- `asset_cache_control`
- `ghost_error_preview_chars`

Used by browser screenshot/render + storage metadata.

## `features`

Feature flags.

- `enable_template_preview`
- `enable_stock_image_search`
- `enable_ai_image_generation`
- `prefer_feature_image`
- `enable_notifications`

## `security`

Security and access-control controls.

### `api_auth`

- `enabled`
- `header_name`
- `require_for_preview`
- `require_for_generate`
- `require_for_direct_content`
- `require_for_webhook`

### `cors`

- `enabled`
- `allowed_origins`
- `allowed_headers`
- `allowed_methods`
- `allow_credentials`
- `max_age_seconds`

### `request_limits`

- `max_json_body_bytes`
- `slot_overrides_max_keys`
- `template_ids_max_keys`

### `rate_limit`

- `enabled`
- `window_seconds`
- `max_requests_per_window`

### `outbound`

- `allow_private_network_targets`
- `allowed_notify_hosts`
- `allowed_image_hosts`

## `storage`

Default R2 key behavior.

- `default_key_prefix`
- `default_mode` (`overwrite` or `versioned`)
- `versioned_include_date`

Request-level `storage` can override these defaults.

## `post_archetypes`

Taxonomy for content intent.

```yaml
post_archetypes:
  default_archetype: insight
  archetypes:
    metric:
      label: Metric
      description: Data-led post centered around one number...
      llm_hint: Best when there are statistics...
```

Used for:

- LLM schema enum for `post_archetype`
- template eligibility filtering (`templates[].archetypes`)

## `slot_schema`

Defines slot defaults and authoring hints.

```yaml
slot_schema:
  defaults:
    headline: "{{TITLE}}"
    metric_value: "2.4K"
  slot_hints:
    headline: "Primary title line used in hero sections."
```

Used for:

- prompt guidance (`<available_slot_keys>` expansion)
- default slot fallback resolution
- preview and runtime slot interpolation behavior

## `generation`

Controls copy/image generation behavior.

### `carousel_required_slides`

Required slide count enforced in normalized output.

### `stock_topic_keywords`

Keyword list that enables stock-image path when topic is concrete.

### `limits`

Hard caps and normalization limits for:

- post/excerpt lengths
- caption lengths
- hashtag lengths/count
- carousel text lengths
- slot text lengths
- storage `runId` length

### `fallbacks`

Fallback text when model output is missing/invalid.

### `llm`

- `default_model`
- `temperature`
- `max_tokens`
- `system_prompt`
- `user_instructions`

Supported placeholders in `user_instructions`:

- `<required_carousel_slides>`
- `<instagram_caption_max_chars>`
- `<twitter_caption_max_chars>`
- `<linkedin_caption_max_chars>`
- `<hashtag_min_count>`
- `<hashtag_max_count>`
- `<available_template_styles>`
- `<available_post_archetypes>`
- `<available_font_profiles>`
- `<available_slot_keys>`

### `image`

- `default_model`
- `prompt_prefix` (prepended to generated `image_prompt`)

## `template_styles`

Visual style taxonomy presented to model and used in template matching.

```yaml
template_styles:
  default_style: editorial
  styles:
    editorial:
      label: Editorial
      description: Magazine-like layouts...
      llm_hint: Best for thoughtful posts.
```

## `formats`

Per-output format config.

Each format defines:

- `width`
- `height`
- `caption_source`
- `hashtag_count`
- `default_template_id`

Current formats:

- `instagram-post`
- `instagram-story`
- `carousel-slide`
- `twitter-card`
- `linkedin-post`

## `preview_defaults`

Default values used by `GET /template/<format>` when query params are omitted.

## `templates`

Template registry entries.

Required fields:

- `id`
- `format`
- `style`
- `label`
- `file`

Optional fields:

- `default_for_style`
- `archetypes`

Example:

```yaml
- id: instagram-post/stat-split
  format: instagram-post
  style: data
  label: Stat Split
  archetypes: [metric]
  file: "../templates/instagram-post/stat-split.html"
```

## Environment vs Config Overrides

Some values can come from request payload, environment variables, and YAML.

Per field precedence:

- brand name/color: request -> env -> YAML
- LLM model: env -> YAML
- image model: env -> YAML
- R2 key prefix: env -> YAML
- notify URL: request -> env
- notify host allowlist: env + YAML
- image host allowlist: env + YAML
- CORS policy: env override (if set) -> YAML

## Common Edit Recipes

### Add a new post archetype

1. add `post_archetypes.archetypes.<id>` with label/description/llm_hint
2. optionally map typography in `typography.selection.by_archetype`
3. assign templates via `templates[].archetypes`
4. run `pnpm run build:templates`

### Add a new style

1. add style entry in `template_styles.styles`
2. add matching render preset if needed (`render.preset_styles`)
3. map font in `typography.selection.by_style`
4. create and register templates using that style

### Change default template per format

1. edit `formats.<format>.default_template_id`
2. confirm template ID exists in `templates`
3. run `pnpm run build:templates`

### Change hashtag policy per platform

1. edit `formats.<format>.hashtag_count`
2. ensure `generation.limits.caption_with_hashtags_max_chars` is still reasonable

## Validation Errors You May See

- `Duplicate template id: ...`
- `Template <id> references unknown format/style/archetype`
- `Format <name> points to missing default_template_id`
- `template_styles.default_style is unknown`
- `post_archetypes.default_archetype is unknown`

Fix YAML and rerun:

```bash
pnpm run build:templates
```
