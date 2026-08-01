# ADR-0004 — Footer Stays LLM-Designed (Verifier-Enforced)

- Status: accepted
- Date: 2026-08-01

## Context
Two options existed for the footer: deterministic programmatic injection
(guaranteed correct) or LLM-designed with exact text passed in the prompt.
LLM design can drift (observed in practice: missing/incorrect footer).

## Decision
Keep the footer **LLM-designed**, with the exact strings passed into the
designer prompt and enforced by the verifier:

1. Deterministic checks fail the design if the name/handle strings are absent.
2. The vision audit scores the footer's placement, rule, and styling.
3. Retry loops feed critique back to the designer.

This keeps the footer flexible to layout while guaranteeing presence.

## Consequences
- A footer can still occasionally be rejected on style grounds and retried.
- No programmatic injection pass is needed; the renderer stays a pure
  injector of tokens/KaTeX/images.
- Revisit this ADR if footer rejection rates stay high after prompt tuning.
