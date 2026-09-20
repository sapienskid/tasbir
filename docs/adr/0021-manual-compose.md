# ADR-0021 — Manual Compose (zero-AI posts) and shared render plumbing

Status: accepted
Date: 2026-09-19

## Context

Some posts need no AI at all: a quote series, an event card, a carousel whose
copy the operator already wrote. Running the strategist/copywriter/designer to
get there wastes quota and gives up control. The template library (ADR-0011),
design languages (ADR-0020), and the rerender path (ADR-0010) already hold
every piece needed to build such a post deterministically.

Two pieces of plumbing were also duplicated across the codebase: "apply a
design language to a design system" (per-post override in `generate_task`,
`POST /design-systems/{id}/style`, and nowhere in rerender), and the
tokens → fonts → KaTeX → images → logo injection sequence (renderer, verifier,
rerender, two template previews, DS preview, template author, chat precheck).

## Decision

### Manual Compose

- New router `/compose`. The operator chooses the design system, design
  language, and ground once per **batch**, then per post a platform and, per
  slide, a template, copy (kicker/headline/subhead/body/tagline/extra), element
  toggles, media position, and media: `none`, `upload`, a stock `photo` (picked
  from `GET /compose/photos`, downloaded through the SSRF-guarded loader), or an
  offline `illustration` (procedural or DiceBear, seeded).
- A batch holds up to 20 posts; a carousel is one post with 2–10 slides. Each
  post becomes its own `GenerationTask` (`source_data.mode = "manual"`, shared
  `batch_id`), so task detail, the editor, rerender, ZIP, and save-as-template
  work unchanged. The full post is stored in `generation_tasks.composition`
  and can be edited and re-rendered via `PUT /tasks/{id}/composition`
  (e.g. a different template, design system, or text).
- The Celery `compose_task` never calls an LLM (enforced by a test): fill the
  template → finalize → render PNG → deterministic checks + overflow +
  low-contrast (the rerender hard gate, no vision audit). Output files and the
  task result use the AI pipeline's exact shape (carousel slides as
  `{base}-{i}`). Whole-task retry of a manual task re-runs `compose_task`; the
  per-format "retry designer" is refused.
- `POST /compose/preview` returns finalized HTML synchronously (no PNG) for the
  composer's live preview. Template list items expose `fields`, `media_kinds`,
  and `has_media`, derived from the template HTML, so the form shows only what
  a template renders. A media kind a template cannot host is ignored.

### Shared plumbing

- `services/ds_context.resolve_ds_context(db_or_pool, ds_id, language)` is the
  single loader: DB row (default fallback, YAML pre-seed fallback) → pipeline
  dicts, plus an optional in-memory language override (palette + accent tokens,
  accent stripped for monochrome languages, `apply_language` on the DI). The
  style-switch route delegates to `design_languages.apply_language_to_system`.
- `services/composer.finalize_html(html, ctx, images, *, katex, grayscale,
  logo)` is the single injection sequence; `fill_template` is shared by the AI
  template node and Manual Compose.

## Consequences

- Operators can produce on-brand posts instantly at zero LLM cost, and
  re-render them later against another template or design system.
- Rerender now honors a task's per-post design-language override.
- The AI per-post override now strips accent tokens for monochrome languages
  (previously a colorful DS kept its accent under a monochrome override).
- Upload bytes live in the composition JSON (≤ 10 MB each), so manual tasks
  are heavier rows than AI tasks.

## Alternatives considered

- A single task per batch (rejected — every downstream view is per task).
- Letting the vision audit gate manual posts (rejected — zero-AI is the point;
  it stays available on demand through the rerender endpoint).
