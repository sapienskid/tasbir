# Template System

Templates define structure. Utility-first CSS tokens define design.

## Purpose

The template system lets you:

- add new layouts without changing renderer code
- keep slot contracts explicit (`{{SLOT:key}}`)
- bind content requirements to selected templates at runtime

## File Roles

- `templates/*.html`: content layouts (the skeletons)
- `templates/system/content-shell.html`: shared runtime shell + stylesheet/token injection
- `src/styles/template.css`: style source compiled during build
- `src/generated/template.css`: compiled stylesheet embedded into runtime assets

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

Those keys become `required_slot_keys` and are used by runtime orchestration to ensure renderable output.

Slot value precedence:

1. request `slotOverrides` (highest)
2. generated/provided slot content
3. runtime fallback inference by slot key pattern (safety net)

## Template Selection Behavior

Per format:

1. use request `templateIds[format]` when provided
2. otherwise ask LLM planner to select from candidate template IDs
3. validate and fallback to format default template if needed

Candidate list is auto-derived from template files discovered under `templates/` and filtered by optional `@formats` constraints.

## Template Dependency Challenge (Agentic Orchestration)

Slot differences across templates remain the core constraint, even with agentic generation.

Recommended contract:

1. planner agent chooses `templateIds` per platform/post type
2. runtime extracts `required_slot_keys` from selected templates
3. copy agent must return `slot_content` that satisfies required keys
4. render guard agent validates fit/completeness before screenshot step
5. fallback policy either:
- re-prompt copy agent with missing keys
- or fill deterministic slot defaults

This keeps template evolution safe without silent rendering failures.

## Agentic Prompt + Render Policy Integration

With SDK-based orchestration enabled, template selection and slot generation are influenced by central prompt profiles:

- profile source: `config/pipeline/content.yaml` (`generation.agents.prompt_profiles`)
- planner guidance: `template_planner` role notes are merged into template planner instructions
- copy guidance: `copywriter` and `strategist` notes are merged into structured copy generation
- visual safety: render policy sanitizes visual slot text before template render

Current render-policy actions in runtime:

- strip hashtags from visual slot payloads when `strip_hashtags_in_visual_slots` is enabled
- remove markdown/math/diagram syntax from visual text when those modes are disabled
- append explicit no-text directives to AI image prompts when `allow_text_in_ai_images=false`

## Rich Content Rendering (Implemented)

The runtime now renders rich syntax directly in template text fields and slot content:

- markdown: rendered via `markdown-it` with HTML disabled (`html: false`)
- math: `$...$` and `$$...$$` rendered via KaTeX (`renderToString`, MathML output)
- diagrams: fenced Mermaid blocks (```mermaid ... ```) converted to placeholders server-side, then to SVG client-side before screenshot

Current mode selection:

1. core body fields (`{{BODY}}`, `{{CAPTION}}`) render in block mode
2. headline/meta fields render inline mode
3. slots use key heuristics (metadata-ish keys inline, narrative keys block)

Render lifecycle:

1. template interpolation emits rich HTML wrappers (`rich-text`, `rich-math`, `rich-mermaid`)
2. content shell runs embedded Mermaid runtime
3. browser screenshot waits for `window.__RICH_RENDER_DONE__ === true`

This fixes literal markdown/math/mermaid source appearing in final PNGs.

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

- `GET /template/<format>?templateId=layout/grid-item-card`

## Add a New Shared System Fragment

1. Add HTML file under `templates/system/`, for example `badge-shell.html`.
2. Rebuild assets.
3. Reference it from `templates/system/content-shell.html` when needed.

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

Screenshot preview:

```text
/preview/screenshot?format=linkedin-post&templateId=layout/split-hero
```

## Troubleshooting Quick Checks

1. confirm template file exists under `templates/`
2. run `pnpm run build:templates`
3. verify `default_template_id` for target format
4. test direct preview with `templateId`
5. verify slot keys match template `{{SLOT:key}}` names

See [Troubleshooting](troubleshooting.md) for full list.
