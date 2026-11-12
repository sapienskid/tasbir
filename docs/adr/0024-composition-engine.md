# ADR-0024 — One composition engine for illustrations and covers

Status: accepted
Date: 2026-11-12

## Context

Illustrations had accumulated four drawing engines and five catalogs:

- `illustration.py` — 65 hand-written "archetypes", most of them a pale blob
  carrier plus one to three lines or dots, with hardcoded positions. The seed
  only changed harmonic wobble and stroke amplitude.
- `illustration_editorial.py` — eight frozen Bézier figures (hand, book,
  vessel …) reused verbatim on every post.
- `procedural_art.py` — 22 full-bleed 1600×900 field motifs dropped into a
  400×240 slot. They cropped, and their `box()` claimed the whole frame, so the
  "safe frame" guarantee did not hold for them.
- `generative_art.py` — three subject grammars used only for `field-synthesis`.
- `covers.py` — its own `COVER_MOTIFS` catalog aliasing all of the above, plus
  string-replacement positioning (`x = width * 0.1`) that cropped or letterboxed
  the art regardless of placement.

Measured consequences:

- 14 of 65 archetypes were "blob + lines"; 19 were field textures; 10 were
  frozen authored figures. The rest were one mark plus a carrier.
- `_archetype_for` picked uniformly from 65, so a 10-slide carousel had a ~52%
  chance of repeating a composition. Nothing prevented repeats across posts.
- The media director's `theme` had no semantic effect: it was substring-matched
  against a table of shape names. The plan's rationale never reached the art.

## Decision

Replace all of it with one engine, `backend/app/services/art/`.

### A scene is a composition, not a shape list

`Scene(concept, subject, relation, field, framing)`. Four independent axes:

- **subjects** (17): figurative but abstract, parameterized by seed (leaf count,
  stem arc, vessel fill, arch nesting, satellite count, approach angle …).
- **relations** (9): occlude, intersect-at-node, cradle, emerge-from,
  converge-to, frame, split, sequence, scale-asymmetry. A relation changes the
  subject's scale, anchor and paint order, and the field is built *around* the
  subject — which is what makes two combinations different pictures.
- **fields** (12): grid, bands, contour, hatch, stipple, halftone, flow,
  phyllotaxis, nodes, rays, waves, dot-matrix. Generated **inside** the safe box,
  at the slot's aspect, so clipping is impossible by construction.
- **framings** (5): centred, left/right third, bottom-anchored, bleed.

Space: 17 × 9 × 12 × 5 ≈ 9,000 structural scenes, plus continuous geometry per
seed. The old "different blob" axis is gone.

### Semantics drive the choice

The director picks a **concept** (limit, growth, system, attention,
convergence, choice, scale, memory, flow, craft). A concept maps to candidate
subjects / relations / fields; the composer selects deterministically from
`(seed, avoid)`. `subject` / `relation` / `field` remain optional pins. Legacy
motif ids and archetype ids still resolve through `LEGACY_COMBOS`; `theme`
keyword-maps to a concept, and `anthropic` aliases `procedural`.

### Variety is enforced

- After the plan is parsed, `media_plan` resolves every illustration to a
  concrete triple and enforces: no `subject|relation` pair twice in one post.
  Concept vocabularies are sized so 10-slide carousels can satisfy this.
- A Redis ring buffer (24 entries, 30 days, per design system) soft-avoids the
  combinations recent posts used. The composer stays pure; callers pass `avoid`.
- Tests assert structural diversity over 200 seeds (distinct fingerprints,
  subject/relation/field coverage, no subject > 25%), zero safe-frame escapes,
  and zero carousel pair collisions across every concept.

### Covers use the same engine

`compose_cover_scene` composes the subject inside a 12% safe frame and lets the
field bleed to the canvas edge (fields may bleed, subjects may not). Placement
left/center/right moves the focal subject, not the finished SVG. Variations
avoid the previous variation's fingerprints. `COVER_MOTIFS` is derived from the
catalog, and `/covers/meta` now publishes concepts, subjects, relations and
fields.

### Guarantees

- Deterministic: same `(seed, avoid)` → byte-identical SVG.
- Token-only: `var(--color-*)`; no hex, no text, no emoji. Accent is a single
  emphasis mark, only when the design language defines it.
- Safe: every element has authoritative bounds; a final uniform fit is a safety
  net, not the normal path.
- Portraits remain DiceBear, wrapped as one style of the same tool.

## Consequences

- `procedural_art.py`, `generative_art.py`, `mathematical_art.py` and
  `illustration_editorial.py` are deleted, along with their tests.
- Public entry points are preserved: `generate_illustration_svg`,
  `generate_figure_metrics`, `run_illustrate`, `ILLUSTRATE_TOOL`,
  `render_illustration`, `build_cover_svg`, `/covers/meta`.
- `app/tools/art_gallery.py` renders a labeled contact sheet; the engine is
  judged visually before shipping a catalog change.
- The Studio's compose picker and cover picker read the published catalog
  instead of maintaining a second list.
