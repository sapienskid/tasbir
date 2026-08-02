# ADR-0011 — Template-Driven Composition with a Learning Library

- Status: accepted
- Date: 2026-08-02
- Related: ADR-0010 (manual edit/re-render), ADR-0007 (ephemeral delivery)

## Context

The designer LLM composed every post from scratch. Output was clean but
formulaic — symmetric stacks, generic copy, an unmistakable "AI poster" look.
Great prompts cannot fix this, because an LLM samples the *average* layout
from its training data every time. The operator wants posts that are hard to
recognize as machine-made, in strict monochrome.

## Decision

Compositions are **human-authored templates**; the LLM writes copy only.

- **Library**: `data/design_system/templates/{family}/*.html` — hand-crafted
  Jinja2 documents with pure CSS (`var(--color-*)`, no framework) and
  `data-slot` attributes on every content element. Jinja2 (already a
  dependency via `fastapi[standard]`) provides autoescaping, optional-slot
  conditionals, and template caching.
- **Selection**: `select_template()` filters by format family + resolved
  ground, boosts by category affinity, honors the strategist's new
  `template_hint` (the strongest signal), adds seeded jitter, and excludes a
  Redis "recently used" list so consecutive posts never repeat.
- **Pipeline**: each format chain tries the template first
  (`template_node_single`). If nothing matches — or the chosen template fails
  QC (e.g. overflow) — it falls back to the LLM designer. Template posts skip
  the designer LLM (faster, cheaper, fewer retries).
- **Learning loop**: `POST /tasks/{id}/formats/{fmt}/template` promotes any
  rendered or operator-edited post into the library. `data-slot` lets the
  prompter read each slot's text directly (robust even after the user edited
  the copy), converts baked base64 images back to `data-image-key` markers,
  strips injected token/font/KaTeX blocks, and re-parameterizes the canvas
  size. Promoted templates are validated (render + overflow) before saving —
  either as a new template or an update of the source template the post came
  from (the Studio default).

## Consequences

- Output quality is bounded by the human-authored templates, not LLM sampling.
- Copy stays the LLM's job; the copywriter prompt now bans filler/clichés and
  demands real specifics.
- The anti-repeat Redis list keeps the feed varied — a core anti-AI tell.
- Promoting edits back into the library means the design system improves with
  use, and the Studio "Save as Template" button is the two-way gate.
