# Template System

## Goal

Templates are externalized as HTML and driven by a slot schema so one renderer can support many post patterns (insight, metric, quote, checklist, promo, timeline).

## Source of truth

- Templates: `templates/**/*.html`
- Registry + behavior: `config/pipeline.config.yaml`
- Generated runtime module: `src/generated/template-assets.ts`

## Build pipeline

Run:

```bash
pnpm run build:templates
```

The build step validates:
1. config shape
2. style/archetype/format references
3. default template IDs
4. template file existence

Then it embeds all template HTML into generated runtime assets.

## Placeholder system

Built-in placeholders:
- `{{TITLE}}`
- `{{CAPTION}}`
- `{{HEADING}}`
- `{{BODY}}`
- `{{BRAND_NAME}}`
- `{{HEADER}}`
- `{{FOOTER}}`
- `{{KICKER}}`
- `{{CONTENT_INSET}}`
- `{{CONTENT_MAX_WIDTH}}`
- `{{CAPTION_MAX_WIDTH}}`
- `{{ALIGNMENT_STYLE}}`

Slot placeholders:
- `{{SLOT:headline}}`
- `{{SLOT:metric_value}}`
- `{{SLOT:quote_text}}`
- `{{SLOT:step_1}}`

Notes:
- Slot values are HTML-escaped.
- `HEADER`, `FOOTER`, and `KICKER` are injected HTML fragments.
- Unknown placeholders resolve to empty strings.

## Selection logic

Per format, runtime template choice is:
1. request `templateIds[format]`
2. match `templateStyle + postArchetype`
3. match `postArchetype`
4. match `templateStyle`
5. `formats.<format>.default_template_id`

If a template has `archetypes`, it is only eligible for those archetypes.

Font profile choice is:
1. request `fontProfile`
2. model `font_profile`
3. config map `typography.selection.by_style`
4. config map `typography.selection.by_archetype`
5. `typography.default_font_profile`

## Request controls

API controls:
- `templateStyle`
- `postArchetype`
- `fontProfile`
- `templateIds`
- `slotOverrides`

Model output controls:
- `template_style`
- `post_archetype`
- `font_profile`
- `slot_content`

`slotOverrides` always wins over model-generated `slot_content`.

## Preview controls

`GET /template/<format>` accepts:
- `templateStyle`
- `templateId`
- `templateArchetype` (or `archetype`)
- `fontProfile`
- slot query keys via `slot.<name>=...` or `slot_<name>=...`

Generated preview HTML includes:
- `data-template-id`
- `data-template-style`
- `data-template-archetype`
