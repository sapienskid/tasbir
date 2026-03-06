# Configuration Reference

Main entrypoint:

- `config/pipeline.config.yaml`

Composed fragments:

- `config/pipeline/templates.yaml`
- `config/pipeline/content.yaml`
- `config/pipeline/runtime.yaml`

`pipeline.config.yaml` uses `extends` to merge these fragments.

## Build Integration

`pnpm run build:templates`:

1. merges config fragments
2. auto-discovers templates from `templates/*.html`
3. validates template compatibility/defaults
4. embeds templates + CSS into `src/generated/template-assets.json`

Run this after any config, template, or CSS change.

## Active Top-Level Sections

Current merged config uses:

- `schema_version`
- `brand`
- `formats`
- `preview_defaults`
- `templates`
- `generation`
- `runtime`
- `features`
- `security`
- `storage`

## `schema_version`

Numeric schema revision.

```yaml
schema_version: 1
```

## `brand`

Default identity values.

```yaml
brand:
  default_name: Tasbir Blog
  default_color: "#1f7a8c"
```

Request/env overrides can replace these at runtime.

## `formats`

Per-platform output metadata.

Each format entry includes:

- `width`
- `height`
- `caption_source`
- `hashtag_count`
- `default_template_id`

Example:

```yaml
formats:
  twitter-card:
    width: 1200
    height: 630
    caption_source: twitter_caption
    hashtag_count: 0
    default_template_id: layout/statement-cta
```

## `preview_defaults`

Fallback values for `GET /template/<format>` when query params are missing.

## `templates`

Auto-generated template registry.

Each item supports:

- `id` (required)
- `label` (required)
- `description` (optional)
- `file` (required)
- `format` or `formats` (optional format restrictions)

`templates` is generated from template front-matter. To constrain compatibility, add `@formats: format-a,format-b` in template HTML comments.

## `generation`

Generation behavior and limits.

### `carousel_required_slides`

Default required carousel slide count.

### `limits`

Hard limits for:

- source text lengths
- caption lengths
- carousel text lengths
- hashtags
- slot content lengths
- request option constraints (for example runId length)

### `fallbacks`

Fallback strings used when model output is incomplete.

### `llm`

- `default_model`
- `temperature`
- `max_tokens`
- `system_prompt` (string array)
- `user_instructions` (string array)
- `template_planner.system_prompt` (string array)
- `template_planner.user_instructions` (string array)

Supported placeholders in `user_instructions`:

- `<required_carousel_slides>`
- `<instagram_caption_max_chars>`
- `<twitter_caption_max_chars>`
- `<linkedin_caption_max_chars>`
- `<carousel_heading_max_chars>`
- `<carousel_body_max_chars>`
- `<hashtag_min_count>`
- `<hashtag_max_count>`
- `<available_slot_keys>`
- `<required_slot_keys>`
- `<template_composition_directives>`

### Current System Prompts (Verbatim)

`generation.llm.system_prompt`:

```yaml
generation:
  llm:
    system_prompt:
      - "You are a senior social growth strategist and marketing copywriter for a personal tech/lifestyle brand."
      - "Write persuasive but credible platform-native copy with a clear value proposition."
      - "Use concrete benefits, audience pain points, and action-oriented language."
      - "Do not invent facts that are not present in the source material."
      - "Always respond with strict JSON matching the required schema."
```

`generation.llm.template_planner.system_prompt`:

```yaml
generation:
  llm:
    template_planner:
      system_prompt:
        - "You are an expert template planner for social content automation."
```

Additional runtime directives injected in code for text generation:

- `Treat templates as structure-only skeletons and place all design decisions in CSS classes.`
- `Fill slot_content comprehensively so every likely template slot has useful copy.`
- `Never request generated text in images; typography is always rendered by the template system.`
- `Keep slot values concise, specific, and directly usable without extra formatting.`

### Proposed Central Prompt Registry (Design Only)

To support role-based agent orchestration with one place to customize behavior, add a central prompt map:

```yaml
generation:
  agents:
    prompt_profiles:
      default:
        mastermind: |
          You are the marketing mastermind for multi-platform campaign generation.
          Optimize for clarity, novelty, platform-native behavior, and visual-text balance.
        roles:
          strategist: |
            Plan platform counts, narrative arcs, and audience intent.
          template_planner: |
            Choose templates that match content semantics and slot constraints.
          copywriter: |
            Create copy per platform and per post type with strict length controls.
          visual_director: |
            Select image strategy and enforce no text artifacts in generated images.
          render_guard: |
            Validate markdown/math/diagram rendering and prevent overflow/hidden text.
```

Recommended behavior:

- each role prompt inherits `mastermind` baseline instructions
- profile key can be selected per request (`agent.promptProfile`)
- prompt versions should be tracked in responses for reproducibility

### `image`

- `default_model`
- `prompt_prefix`
- `negative_clauses`

Note: image generation currently does not use a chat-style `system_prompt`; it composes a single prompt string using `prompt_prefix`, title, tags, scene description, and negative clauses.

## `runtime`

Runtime constants:

- `browser_keep_alive_ms`
- `page_set_content_wait_until`
- `asset_cache_control`
- `ghost_error_preview_chars`

## `features`

Feature toggles:

- `enable_template_preview`
- `enable_ai_image_generation`
- `prefer_feature_image`
- `enable_notifications`

## `security`

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

Default storage behavior:

- `default_key_prefix`
- `default_mode` (`overwrite` or `versioned`)
- `versioned_include_date`

Request-level `storage` can override these.

## CSS and Design Tokens

Design tokens are not configured in YAML.

Use:

- `src/styles/template.css` for spacing, typography, color-token usage, semantic classes
- template CSS variables and class utilities for visual control

## Optional Advanced Sections

Runtime also supports optional advanced sections if you add them to config:

- `theming`
- `render`

If omitted, code-level defaults are used.
