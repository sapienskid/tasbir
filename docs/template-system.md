# Template System

This project renders social assets from reusable HTML templates with config-driven selection logic.

The goal is to let you add or modify designs without changing rendering code.

## Core Concepts

- `template_style`: visual look (editorial, minimal, bold, data, illustration)
- `post_archetype`: content intent (insight, metric, quote, checklist, timeline, promo)
- `slot_content`: semantic content fields used by templates (`headline`, `metric_value`, `quote_text`, etc.)

A template can target a style, one or more archetypes, or both.

## Sources of Truth

- template files: `templates/**/*.html`
- registry + constraints: `config/pipeline.config.yaml` (`templates:` section)
- generated runtime bundle: `src/generated/template-assets.ts`

## Build Pipeline

Run after template or config changes:

```bash
pnpm run build:templates
```

Or full asset build:

```bash
pnpm run build:assets
```

Validation includes:

- config shape checks
- duplicate template ID detection
- unknown format/style/archetype detection
- missing default template IDs
- missing template file path detection

## Template File Rules

Use `.html` files.

- put file under `templates/<format>/`
- use token placeholders like `{{TITLE}}`
- use slot placeholders like `{{SLOT:headline}}`
- do not add script execution logic in template files

## Placeholder Types

### Built-in Tokens

- `{{TITLE}}`
- `{{CAPTION}}`
- `{{HEADING}}`
- `{{BODY}}`
- `{{BRAND_NAME}}`
- `{{TEMPLATE_ARCHETYPE}}`
- `{{HEADER}}`
- `{{FOOTER}}`
- `{{KICKER}}`
- `{{CONTENT_INSET}}`
- `{{CONTENT_MAX_WIDTH}}`
- `{{CAPTION_MAX_WIDTH}}`
- `{{ALIGNMENT_STYLE}}`

Notes:

- `HEADER`, `FOOTER`, and `KICKER` inject controlled HTML fragments
- other values are escaped before insertion

### Slot Tokens

Pattern:

- `{{SLOT:<slot_key>}}`

Examples:

- `{{SLOT:headline}}`
- `{{SLOT:metric_value}}`
- `{{SLOT:quote_text}}`
- `{{SLOT:step_2}}`

Slot keys are normalized:

- lowercased
- non-alphanumeric characters become `_`
- repeated `_` collapse to single `_`

## Slot Value Precedence

When rendering, slot values are merged in this order:

1. YAML defaults (`slot_schema.defaults`)
2. model-generated `slot_content`
3. request `slotOverrides`

`slotOverrides` always wins.

## Template Selection Logic

Per format, the resolver chooses template in this order:

1. explicit request `templateIds[format]`
2. templates matching `templateStyle + postArchetype`
3. templates matching `postArchetype`
4. templates matching `templateStyle`
5. `formats.<format>.default_template_id`
6. first configured template for format (final safety fallback)

If template defines `archetypes`, it is only eligible for those archetypes.

## Font Selection Logic

Font profile is resolved in this order:

1. request `fontProfile`
2. model output `font_profile`
3. `typography.selection.by_style`
4. `typography.selection.by_archetype`
5. `typography.default_font_profile`

## Add a New Template (Step by Step)

Example: add a new Instagram metric card.

1. Create HTML file:

- `templates/instagram-post/metric-pill.html`

2. Use placeholders in the file:

```html
<section class="..." style="{{ALIGNMENT_STYLE}}">
  {{HEADER}}
  <p>{{SLOT:kicker}}</p>
  <h1>{{SLOT:metric_value}}</h1>
  <p>{{SLOT:metric_label}}</p>
  <p>{{SLOT:headline}}</p>
  {{FOOTER}}
</section>
```

3. Register it in YAML:

```yaml
- id: instagram-post/metric-pill
  format: instagram-post
  style: data
  label: Metric Pill
  archetypes: [metric]
  file: "../templates/instagram-post/metric-pill.html"
```

4. Rebuild:

```bash
pnpm run build:templates
```

5. Preview:

```bash
curl "http://127.0.0.1:8787/template/instagram-post?templateId=instagram-post/metric-pill&archetype=metric&slot.metric_value=84%25&slot.metric_label=Completion&slot.headline=Process%20drives%20results"
```

6. If successful, include it in API generation via `templateIds.instagram-post` or allow auto-selection.

## Current Template Catalog

Configured templates by format:

### `instagram-post`

- `instagram-post/editorial`
- `instagram-post/illustration`
- `instagram-post/grid` (metric)
- `instagram-post/stat-split` (metric)
- `instagram-post/quote-focus` (quote)
- `instagram-post/checklist` (checklist, timeline)

### `instagram-story`

- `instagram-story/spotlight`
- `instagram-story/illustration` (insight, quote)
- `instagram-story/timeline` (timeline, checklist)
- `instagram-story/promo-banner` (promo)

### `carousel-slide`

- `carousel-slide/minimal`
- `carousel-slide/illustration` (insight)
- `carousel-slide/quote` (quote)
- `carousel-slide/step-card` (checklist, timeline)
- `carousel-slide/stat-card` (metric)

### `twitter-card`

- `twitter-card/bold`
- `twitter-card/data-strip` (metric)
- `twitter-card/editorial`
- `twitter-card/quote-focus` (quote)
- `twitter-card/promo-pill` (promo)

### `linkedin-post`

- `linkedin-post/clean`
- `linkedin-post/editorial`
- `linkedin-post/illustration` (insight, promo)
- `linkedin-post/checklist` (checklist, timeline)
- `linkedin-post/quote-insight` (quote)

## Preview Query Cookbook

Style and archetype preview:

```text
/template/twitter-card?templateStyle=bold&archetype=promo
```

Direct template preview:

```text
/template/linkedin-post?templateId=linkedin-post/checklist
```

Slot override preview:

```text
/template/carousel-slide?templateId=carousel-slide/step-card&slot.step_number=2&slot.step_total=5&slot.headline=Extract%20the%20signal&slot.body=Turn%20long%20content%20into%20short%20decisions.
```

Font override preview:

```text
/template/instagram-post?fontProfile=data-mono
```

## Debugging Checklist

If template does not appear in output:

1. check template is registered in YAML `templates:`
2. run `pnpm run build:templates`
3. confirm format/style/archetype names are valid
4. confirm `default_template_id` exists for the format
5. test direct preview with `templateId`
6. check `archetypes` filter is not excluding current post archetype

For more issues, see [Troubleshooting](troubleshooting.md).
