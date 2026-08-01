# ADR-0002 — Constrained Body Measure

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0001, ADR-0005

## Context
Full-width body lines at 28px on a 952px content column are too long for
comfortable reading and read as "default". Premium editorial sets copy in a
proper measure (optimal line length).

## Decision
Constrain subhead and body copy to a **measure of ~600px** at the 1080px
canvas, scaled by width/1080 (e.g. ~667px on 1200px landscape, ~556px on
1000px Pinterest). The headline spans the full content width; only support
text is constrained.

## Consequences
- Dramatic scale contrast: full-width headline vs. narrow body column.
- The designer prompt and layout block carry the measure per format.
- The verifier expects support text to respect the measure.
