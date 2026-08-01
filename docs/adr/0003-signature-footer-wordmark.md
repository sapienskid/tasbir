# ADR-0003 — Signature Footer Wordmark

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0001, ADR-0004

## Context
The footer name previously used the same metadata style as the @handle —
functional but anonymous. The brand has no illustrative mark, so typography
is the only signature available.

## Decision
Render the footer **name** ("SABIN POKHAREL") as a **signature wordmark**:
Space Grotesk (`var(--font-display)`), ~24px, weight 500, tight tracking
(−0.01em), uppercase. The **@handle** stays in Inter metadata style (20px,
tracked uppercase, secondary gray). Asymmetric footer = premium detail.

## Consequences
- The name becomes the de-facto logotype — no icon or mark needed.
- Designers must distinguish the wordmark (display face) from the handle
  (body face) in the footer row.
- The verifier's content requirements check both the wordmark and the handle.
