# ADR-0014: Planner agent, live observability, and the DS-hardcode guarantee

**Status:** Accepted · **Date:** v3.6

## Context
Two gaps surfaced once agent configs moved to the DB (ADR-0013):

1. **No structural planning.** The pipeline always built exactly the platforms
   the caller requested. A bare `instagram-carousel` pick got a fixed 3-slide
   square carousel with no per-frame intent; there was no way to let the system
   decide the post structure (single vs carousel vs story), aspect ratio, or
   platform set.

2. **Invisible + unverifiable execution.** Pipeline progress was a hardcoded
   45% in the UI (`progress_callback` was never wired), the Agents graph showed
   configuration only, and design-system content (fonts, hex, type sizes, token
   names) was hardcoded in several agent prompt paths — drifting from the
   active design system.

## Decision

### Planner agent (hybrid, user-intent-wins)
- New **planner** agent (`config/prompts/planner.yaml`, `nodes/planner.py`,
  `PostPlan` in `state.py`) sits between the strategist and the copywriter:
  `post_type` (single|carousel|story), `ratio` (square|portrait), `slides`
  (2-10), `platforms`, and a per-slide `slides_outline`.
- **Hybrid gating**: the LLM plans only when the structure is undecided —
  `platforms` contains `"auto"`, or a carousel was requested with an unpinned
  `slides`/`ratio`. Otherwise the plan is synthesized deterministically from
  the request (zero extra LLM cost, trace readout always present).
- **User intent wins**: explicit `slides`/`ratio`/platforms are authoritative;
  the planner only fills gaps. The resolved carousel base follows `ratio`
  (portrait → `instagram-carousel-portrait`, added to `platforms.yaml`).

### Sequence check
- Deterministic, always, for carousels: every slide must share the same canvas
  dims and carry its `i/N` counter (missing counter = soft warning).
- Opt-in vision set-pass (`sequence_audit`): the whole slide set is rendered as
  one grid and audited once (cohesion / repetition / flow).

### Live observability
- `generation_tasks.progress` JSON column (`_ensure_column` migration); the
  Celery task wires the existing `run_pipeline` progress callback.
- `GET /api/tasks/{id}/progress` → `{pct, node, per_format, done, total}`;
  per-format state is derived from the audit timeline while running, from the
  stored result when settled.
- Task-detail replaces the fake progress card with a real bar + per-format
  chips; the Trace tab polls while running; the Agents page overlays runtime
  state on the pipeline graph and shows a live-run card.

### No hardcoded design info in agents (the guarantee)
- `resolve_ground_vars()` in the token service replaces the designer's
  hardcoded ground→variable map (agents receive variable NAMES only).
- The designer's emergency fallback HTML is fully design-system-driven (fonts
  link + type sizes + ground vars come from tokens/DI, never literals).
- Font-face fallbacks in code use `DEFAULT_TOKEN_VALUES` (the DS seed) instead
  of inline face names; the design-instruction prompt formatter no longer
  embeds faces.
- A regression test (`tests/test_agents/test_no_hardcoded_ds.py`) scans the
  prompts + agent prompt-assembly code for hex/font/brand/category literals and
  fails if any creep back in.

## API surface additions
- `POST /api/generate`: `ratio` (`square`|`portrait`|`auto`), `sequence_audit`,
  `platforms` accepts `"auto"`.
- `GET /api/tasks/{id}/progress`; `GET /api/tasks/{id}` includes `progress`,
  and results include `post_plan` + `sequence_check`.

## Future
- Human-in-the-loop planning approval (interrupt after the planner, before the
  copywriter) — see ADR-0013 checkpoint/HITL notes.
