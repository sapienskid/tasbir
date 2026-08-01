# ADR-0001 — Two-Family Typographic System

- Status: superseded by ADR-0006 (extended to a three-voice system)
- Date: 2026-08-01
- Related: ADR-0002, ADR-0003, ADR-0005, ADR-0006

## Context
The Swiss baseline was technically correct but generic — a single grotesque
face (Inter) at fixed sizes reads as a default template, not as a brand. The
goal is modern tech-editorial quality (Linear, Stripe, Framer): recognizable,
confident typography within the strict monochrome Swiss system.

## Decision
Introduce a **two-voice type system**:

- **Display voice — Space Grotesk** (`var(--font-display)`). Used ONLY for the
  headline and the footer wordmark. Big, tight, confident.
- **Body voice — Inter** (`var(--font-sans)`). Every other element: category
  kicker, subhead, body, metadata, handle. Quiet.

Per-family weight limit of 2 (Space Grotesk 500+700, Inter 400+500), keeping
the austere discipline while allowing the display face its own expressive
weight.

## Consequences
- Every post is instantly recognizable: Space Grotesk = headline/brand.
- The renderer and verifier must know both families (config-driven).
- The old "single family, no mixing" rule is replaced by "display face only
  for headline + wordmark; everything else in the body face".
- A deterministic check requires the display face to actually be used.
