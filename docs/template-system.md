# Template System

This project renders social assets from reusable HTML templates with config-driven selection logic.

The goal is to let you add or modify designs without changing rendering code.

## Core Concepts

- `template_style`: visual look (editorial, illustration, minimal, bold, data, monochrome-swiss, brutal)
- `post_archetype`: content intent (insight, metric, quote, checklist, timeline, promo)
- `slot_content`: semantic content fields used by templates (`headline`, `metric_value`, `quote_text`, etc.)

A template can target one or more styles, one or more archetypes, and one or more output formats.

## Sources of Truth

- template files: `templates/**/*.html`
- registry + constraints: `config/pipeline/templates.yaml` (`templates:` section; merged via `config/pipeline.config.yaml`)
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

- put file under `templates/` for reusable layouts
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
6. first configured template compatible with that format (final safety fallback)

If template defines `archetypes`, it is only eligible for those archetypes.
If template defines `formats`, it is only eligible for those formats.

## Font Selection Logic

Font profile is resolved in this order:

1. request `fontProfile`
2. model output `font_profile`
3. `typography.selection.by_style`
4. `typography.selection.by_archetype`
5. `typography.default_font_profile`

## Add a New Template (Step by Step)

Example: add a reusable metric card for all formats.

1. Create HTML file:

- `templates/metric-pill.html`

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
- id: core/metric-pill
  styles: [data, monochrome-swiss]
  formats: [instagram-post, instagram-story, carousel-slide, twitter-card, linkedin-post]
  label: Metric Pill
  archetypes: [metric]
  file: "../templates/metric-pill.html"
```

4. Rebuild:

```bash
pnpm run build:templates
```

5. Preview:

```bash
curl "http://127.0.0.1:8787/template/instagram-post?templateId=core/metric-pill&archetype=metric&slot.metric_value=84%25&slot.metric_label=Completion&slot.headline=Process%20drives%20results"
```

6. If successful, include it in API generation via `templateIds.instagram-post` or allow auto-selection.

## Current Template Catalog

Configured shared templates:

- `core/editorial-base`
- `core/illustration-base`
- `core/bold-base`
- `core/data-base`
- `core/quote-focus` (quote)
- `core/checklist-stack` (checklist, timeline)
- `core/metric-split` (metric)
- `core/promo-pill` (promo)

## Preview Query Cookbook

Style and archetype preview:

```text
/template/twitter-card?templateStyle=bold&archetype=promo
```

Direct template preview:

```text
/template/linkedin-post?templateId=core/checklist-stack
```

Slot override preview:

```text
/template/carousel-slide?templateId=core/checklist-stack&slot.step_number=2&slot.step_total=5&slot.headline=Extract%20the%20signal&slot.body=Turn%20long%20content%20into%20short%20decisions.
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
