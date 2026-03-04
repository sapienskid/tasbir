# Configuration Reference

Central config file: `config/pipeline.config.yaml`

## Top-level keys

- `schema_version`: config schema version
- `brand`: default brand name/color
- `typography`: font profiles and style/archetype font mappings
- `theming`: token derivation and color engine settings
- `render`: preset styles, frame defaults, control defaults, labels
- `runtime`: browser rendering and storage runtime parameters
- `features`: feature flags
- `storage`: default key-prefix/mode policy
- `post_archetypes`: archetype taxonomy used by LLM + template resolver
- `slot_schema`: slot defaults and slot key hints
- `generation`: LLM/image settings and carousel constraints
- `template_styles`: visual style taxonomy
- `formats`: dimensions + hashtag policy + default template per format
- `preview_defaults`: defaults for `/template/*`
- `templates`: template registry

## Key sections

### `typography`

Defines font profiles and automatic selection maps.

```yaml
typography:
  default_font_profile: editorial-serif
  profiles:
    editorial-serif:
      google_fonts_css2_query: "family=Fraunces..."
  selection:
    by_style:
      data: data-mono
    by_archetype:
      metric: data-mono
```

Used for:
- `llm_output.font_profile`
- automatic font resolution when request does not override

### `post_archetypes`

```yaml
post_archetypes:
  default_archetype: insight
  archetypes:
    metric:
      llm_hint: "Best when there are statistics..."
```

Used for:
- `llm_output.post_archetype`
- archetype-aware template filtering

### `slot_schema`

```yaml
slot_schema:
  defaults:
    headline: "{{TITLE}}"
    metric_value: "2.4K"
  slot_hints:
    headline: "Primary title line..."
```

Used for:
- prompt guidance (`slot_content` key selection)
- runtime slot fallback values

### `render`

Controls visual rendering defaults:
- `preset_styles`
- `control_defaults`
- `format_control_defaults`
- `caption_width_rules`
- `meta_left_labels` / `meta_right_labels`
- `frame_decor`

This makes layout tuning and style tuning fully config-driven.

### `runtime`

Controls runtime constants for browser/storage behavior:
- browser keep-alive
- screenshot page load wait mode
- R2 cache-control header
- Ghost API error preview length

### `generation.llm.user_instructions`

Supports placeholders:
- `<required_carousel_slides>`
- `<available_template_styles>`
- `<available_post_archetypes>`
- `<available_font_profiles>`
- `<available_slot_keys>`

These are expanded at runtime before model invocation.

### `templates`

Required fields:
- `id`
- `format`
- `style`
- `file`

Optional fields:
- `default_for_style`
- `label`
- `archetypes` (restrict template to specific archetypes)

Example:

```yaml
- id: instagram-post/stat-split
  format: instagram-post
  style: data
  archetypes: [metric]
  file: "../templates/instagram-post/stat-split.html"
```

## Validation rules (`pnpm run build:templates`)

- duplicate template IDs
- unknown format/style references
- unknown archetype references
- missing default template IDs
- missing required config sections
