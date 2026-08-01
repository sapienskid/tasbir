# ADR-0006 — Serif Body Voice (Source Serif 4)

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0001 (extends the two-family system to three voices)

## Context
After shipping the two-family system (Space Grotesk display + Inter body),
the direction evolved: serif was wanted "in the system" because serif text
reads as premium editorial. Playfair Display was considered for the display
role but rejected — Space Grotesk stays as the display voice. The serif is
instead the **text voice**.

## Decision
Introduce a third voice, **Source Serif 4** (`var(--font-serif)`), for the
**subhead and body copy**. Space Grotesk keeps the headline + footer wordmark.
Inter keeps the category label, metadata, and handle.

- Subhead: serif, 36px, 400, measure 600px
- Body: serif, 28px, 400, leading 1.4, measure 600px

Per-family weights: Space Grotesk 500+700, Source Serif 4 400, Inter 500.

## Consequences
- Reading text is now serif — literary, premium-editorial quality that also
  flatters the math/AI content.
- The "no serif ever" rule is replaced by "serif only for subhead + body".
  Serif in headlines, category labels, metadata, or the wordmark is forbidden.
- The verifier distinguishes three voices and flags voice bleed.
- KaTeX math fonts remain exempt (math is functional, not typographic).
