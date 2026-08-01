# ADR-0005 — Typographic Control Lives in YAML

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0001, ADR-0002, ADR-0003

## Context
Design values were historically split between YAML and hardcoded Python
(fonts links, CSS variable lists, fallback HTML colors). That split made
"design control from configuration" impossible and the code brittle.

## Decision
All typographic control lives in the design-system YAML:

- `tokens.yaml` — the font families (`--font-sans`, `--font-display`).
- `design-instruction.yaml` — per-role `family`, size, weight, tracking,
  leading, measure, and the footer wordmark spec.

Code reads these files and derives everything else: the Google Fonts link
(families + weights), the CSS variable reference, the per-format layout
block, and the verifier context. No font family, weight, or size is
hardcoded in Python.

## Consequences
- Changing typeface or scale = editing YAML only, no redeploy of logic.
- The designer and verifier prompts are generated from the same source, so
  they can't drift apart.
- Adding a role or family requires updating the YAML (and optionally the
  semantic role map in `tokens.py`).
