# Template System

Templates define structure. CSS tokens define design.

## Purpose

The template system lets you:

- add new layouts without changing renderer code
- keep slot contracts explicit (`{{SLOT:key}}`)
- let LLM fill content according to template requirements

## File Roles

- `templates/*.html`: content layouts (the skeletons)
- `templates/system/head-shell.html`: document head + stylesheet/token injection
- `templates/system/frame-shell.html`: common frame/background wrapper
- `templates/system/*.html`: reusable UI fragments

## Placeholder Types

Standard tokens:

- `{{TITLE}}`
- `{{CAPTION}}`
- `{{HEADING}}`
- `{{BODY}}`
- `{{BRAND_NAME}}`
- `{{HEADER}}`
- `{{FOOTER}}`
- `{{KICKER}}`
- `{{ALIGN_CLASS}}`

Slot tokens:

- `{{SLOT:<key>}}`
- examples: `{{SLOT:headline}}`, `{{SLOT:cta_text}}`, `{{SLOT:metric_value}}`

## Slot Contract Behavior

For each selected template, runtime extracts slot keys from `{{SLOT:key}}` markers.

Those keys become `required_slot_keys` and are enforced in LLM output schema.

Slot value precedence:

1. LLM `slot_content`
2. request `slotOverrides`
3. runtime fallback inference by slot key pattern

## Template Selection Behavior

Per format:

1. use request `templateIds[format]` when provided
2. otherwise ask LLM planner to select from candidate template IDs
3. validate and fallback to format default template if needed

Candidate list is auto-derived from template files discovered under `templates/` and filtered by optional `@formats` constraints.

## Add a New Template

1. Create file under `templates/`, for example `templates/feature-spotlight.html`.
2. Optional front-matter directives:
- `@id`, `@label`, `@description`
- `@formats: twitter-card,linkedin-post` to constrain compatibility
- `@slot` metadata for slot hints/defaults
3. Rebuild assets:

```bash
pnpm run build:templates
```

4. Verify:

- `GET /template-catalog`
- `GET /template/<format>?templateId=layout/grid-item-card`

## Add a New Shared System Fragment

1. Add HTML file under `templates/system/`, for example `badge-shell.html`.
2. Rebuild assets.
3. Render it via `src/templates.ts` using `renderSystemFragment(...)`.

`embed-template-assets.mjs` auto-loads all `templates/system/*.html` files.

## Preview Cookbook

Direct template preview:

```text
/template/twitter-card?templateId=layout/statement-cta
```

Slot override preview:

```text
/template/instagram-square?templateId=layout/statement-cta&slot.headline=Ship%20Faster&slot.supporting_line=One%20pipeline%20for%20all%20formats&slot.cta_text=Read%20Guide
```

Design-control preview:

```text
/template/linkedin-post?templateId=layout/editorial-classic&showMetaFooter=true&textAlign=left&imageOpacity=0.45
```

## Troubleshooting Quick Checks

1. confirm template file exists under `templates/`
2. run `pnpm run build:templates`
3. verify `default_template_id` for target format
4. test direct preview with `templateId`
5. verify slot keys match template `{{SLOT:key}}` names

See [Troubleshooting](troubleshooting.md) for full list.
