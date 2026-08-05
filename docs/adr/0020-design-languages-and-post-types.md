# ADR-0020 — Design languages and post types

Status: accepted
Date: 2026-08-05

## Context

The pipeline originally assumed one visual language (Swiss monochrome
editorial). Every agent prompt, the media plan, photo treatment, and the
verifier hardcoded that assumption, so a "different style" was impossible and
the footer/illustration systems were inconsistent.

We also wanted posts to carry structured variants (product price, event
date/location, a call to action) rather than only kicker/headline/body.

## Decision

### Design languages are DB-backed bundles

- A `design_languages` table stores languages; the five built-ins
  (`swiss-editorial`, `bold-modern`, `dark-luxury`, `vibrant-pop`, `playful`)
  are seeded from `STYLE_PRESETS` and always resolve to the **live** preset
  (edits to `styles.py` propagate without reseeding). Users can create custom
  languages derived from any base and delete them; built-ins are immutable.
- Each language defines a `palette_tokens` bundle (bg/text/border/radius/
  shadow) plus accent tokens. Applying a language **replaces the design
  system's color tokens** (fonts stay user-owned), so switching languages
  visibly changes the palette.
- A design system references a language by `style_language` id and keeps a
  merged copy of its `di` + tokens, so deleting a language never breaks a
  system. The default system is user-owned after an edit (the startup seed-sync
  skips it).

### Every layer reads the language

The style rules block (`build_style_rules_block`) is injected into the designer
and verifier prompts; the media director, photo treatment (grayscale vs
full color), emoji rule, and layout-archetype pool all follow it. Grounds stay
`white`/`black` for every language (colored grounds are out of scope).

### Footer and illustration rules

- The footer is a single `@handle`, no hairline rule, rendered only when
  configured.
- Illustrations are allowed in **designated slots** (`slide`, `ad-card`) for
  every language. The media director skips photo search for conceptual/abstract
  subjects and uses an abstract illustration; if a planned photo can't
  materialize, the slot fills with a procedural figure instead of shipping
  empty.

### Verifier philosophy

Hard gates stay deterministic (canvas, hex, emoji per language, footer, category,
overflow, low-contrast text). The vision audit judges visual quality; a design
that clears every hard gate and scores ≥75 passes despite a strict `pass=false`
(minor spec drift is not a hard fail). `verifier.max_retries` default is 3.

### Post types and copy extras

`POST /generate` accepts `post_type`
(`default|quote|promo|event|product|comparison|tutorial`). The copy schema has an
optional `extra` object; the copywriter fills the keys the post type asks for
(price/date/location/stat/cta/source) from the source, surfaced to the designer
and available to templates as `{{ extra.* }}`. `ad-card` renders price+cta;
`landscape-pull` renders date+location.

## Consequences

- A design system can switch visual language instantly and keep it across
  restarts; custom languages are manageable in the Studio.
- Template-first posts can carry illustrations in the slots that support them.
- LLM-designer posts are far less likely to be rejected for minor spec drift.
- Post types give structured copy variants for product/event/promo content.

## Alternatives considered

- Injecting the footer programmatically (rejected — authoring should own it).
- Adding illustration slots to every template (rejected — only designed slots).
- Keeping languages as code-only presets (rejected — users wanted create/delete).
