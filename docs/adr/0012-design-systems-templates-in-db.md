# ADR-0012: Design Systems and Templates move to the Database

**Status:** Accepted · **Date:** v0.5.0

## Context
Templates and the design system (brand, tokens, campaigns, design-instruction)
lived in YAML files under `data/design_system/`, bind-mounted into containers.
Editing required restarting workers, and there was no way to manage multiple
brands, upload logos, or generate new assets agentically.

## Decision
- **DesignSystem** and **Template** become first-class SQLite entities.
  - `DesignSystem` holds `brand`, `footer`, `categories`, `overrides`,
    `tokens`, `token_roles`, `campaigns`, `design_instruction`, and an
    optional base64 `logo`. `default` is delete-protected.
  - `Template` is scoped to a design system (`design_system_id`) and holds the
    Jinja2 `html`, `image_slots`, `has_logo_slot`, family, grounds, categories,
    hint tags, and weight.
- On first boot the existing YAML config + template files seed a `default`
  design system (idempotent). YAML loaders remain only for seeding/tests.
- Templates are rendered from DB HTML via `env.from_string()`; selection stays
  a pure function over a loaded template list.
- The pipeline resolves tokens/brand/footer/categories/campaigns/design
  instruction/logo from the chosen design system (default: `default`), and a
  user-selected `template_id` is honored for its family with auto-fallback.
- Ground remains a binary `white|black`; "color" comes from per-design-system
  token **values**. Raw hex in template HTML stays forbidden (var-only), so
  full-color brands are safe under the same deterministic QC.

## Agentic creation
- **Template Author** (`template_vision` + `template_author` prompts): a mockup
  image → layout spec → Jinja2 HTML → validation loop (sample-copy render +
  overflow + deterministic QC with retry-on-critique) → saved Template.
- **Brand Builder** (`brand_vision`, `brand_tokens`, `brand_campaigns`): a form
  (+ optional reference/logo images) → brand brief → tokens + DI overlay from a
  curated Google Fonts pool → campaign presets → starter square/landscape
  templates → saved DesignSystem.
- Both run as background `AgentJob`s via Celery, polled at `GET /agent-jobs/{id}`.

## New API surface
`GET/POST /design-systems`, `GET/PUT/DELETE /design-systems/{id}`,
`POST/DELETE /design-systems/{id}/logo`, `POST /design-systems/{id}/preview`,
`POST /design-systems/from-input`, `GET/POST /templates`,
`GET/PUT/DELETE /templates/{id}`, `POST /templates/{id}/render`,
`POST /templates/{id}/preview`, `POST /templates/from-image`,
`GET /agent-jobs/{id}`, `POST /uploads`.

## Consequences
- Multiple brands with independent tokens/campaigns/templates/logo.
- Full in-UI editing (forms + advanced JSON editors) with live preview.
- `POST /generate` now accepts `design_system_id` and `template_id`.
- Promoted posts ("save as template") persist to the DB.
- The 16 hand-authored templates are preserved via the seed.
