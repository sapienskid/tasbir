# Social Media Asset Pipeline Worker

Cloudflare Worker that generates social-ready assets from blog content using Ghost + Workers AI + Browser Rendering + R2.

## What this now supports

The system is now `template + slot schema` based:
- HTML templates in `templates/**/*.html`
- central configuration in `config/pipeline.config.yaml`
- archetype-aware template selection (`insight`, `metric`, `quote`, `checklist`, `timeline`, `promo`)
- automatic font-profile selection (AI + config mappings by style/archetype)
- slot-driven content (`slot_content`) for flexible layouts

This makes it possible to support many post structures without hardcoding new renderer functions.

## `.html` vs `htmlx`

Use `.html`.
- `.html` is the standard format and has universal tooling support.
- `htmlx` is not a web-standard template format.
- If you meant **htmx**, it still uses regular `.html` files.

References:
- https://developer.mozilla.org/en-US/docs/Web/HTML
- https://html.spec.whatwg.org/
- https://htmx.org/docs/

## Project structure

- `config/pipeline.config.yaml`: source of truth for styles/archetypes/formats/templates/slots
- `templates/**/*.html`: template files
- `scripts/embed-template-assets.mjs`: compile YAML + HTML into runtime module
- `src/generated/template-assets.ts`: generated config/template assets
- `src/templates.ts`: template resolver + slot interpolation
- `src/index.ts`: API + orchestration

## Setup

```bash
pnpm install
pnpm run build:assets
cp .dev.vars.example .dev.vars
pnpm run dev
```

Deploy:

```bash
pnpm run deploy
```

## API

### `POST /generate`

```json
{
  "slug": "my-post-slug",
  "templateStyle": "data",
  "postArchetype": "metric",
  "fontProfile": "data-mono",
  "templateIds": {
    "instagram-post": "instagram-post/stat-split"
  },
  "slotOverrides": {
    "metric_value": "2.4K",
    "metric_label": "Monthly signups",
    "headline": "Growth with less noise"
  }
}
```

### `POST /generate-from-content`

```json
{
  "title": "A post without Ghost",
  "content": "Plain content for testing.",
  "templateStyle": "editorial",
  "postArchetype": "quote",
  "fontProfile": "editorial-serif"
}
```

### `GET /template/<format>`

Preview template HTML.

Examples:
- `/template/instagram-post?templateId=instagram-post/stat-split&archetype=metric&slot.metric_value=9.8K`
- `/template/twitter-card?templateStyle=bold&templateArchetype=promo&fontProfile=bold-campaign&slot.cta_text=Read+Now`

## Selection behavior

Per format, template resolution order:
1. `templateIds[format]`
2. `templateStyle + postArchetype`
3. `postArchetype`
4. `templateStyle`
5. YAML `default_template_id`

## Docs

- [Architecture](docs/architecture.md)
- [Template System](docs/template-system.md)
- [Config Reference](docs/config-reference.md)
- [Research Summary](docs/research-summary.md)
- [Design Principles](docs/design-principles.md)

## Commands

- `pnpm run build:assets`
- `pnpm run check`
- `pnpm run test`
