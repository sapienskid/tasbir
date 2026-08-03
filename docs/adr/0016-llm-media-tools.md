# ADR-0016 — LLM-Callable Media Tools (photos + hand-drawn illustrations)

- Status: accepted
- Date: 2026-08-03
- Related: ADR-0009 (SSRF), ADR-0015 (config in DB), ADR-0017 (attribution policy)

## Context

The illustration generator (ADR: Anthropic-style procedural SVG) proved the
tool pattern, but a strict procedural generator can't deliver real photos or
the hand-drawn people/scenes users expect from the "editorial" brand. We
needed stock photos and CC0 hand-drawn illustration kits, while keeping three
invariants:

1. **Monochrome brand** — "no hue, ever". Photos and kits must render grayscale.
2. **Verifier-safe output** — no raw hex anywhere in the final HTML; only
   `var(--color-*)`.
3. **Zero API cost target** — free tiers only, degrade gracefully without keys.

Research findings: Pixabay requires downloading (no hotlinking) and 24h search
caching; Pexels offers 200 req/hr free with an exactly-1200×627 landscape crop;
Unsplash requires hotlinking (conflicts with our base64 pipeline) and has a
50/hr demo tier — rejected as primary. Wikimedia Commons is keyless but
requires a descriptive User-Agent and honors CC licenses that mandate
attribution. Pablo Stanley's **Open Peeps / Open Doodles** are CC0 (public
domain) and vendorable into the repo.

## Decision

Expose two new LLM function-calling tools alongside the existing
`illustrate`-style director, behind a small tool registry
(`app/services/tools/`):

- **`find_photo(query, orientation?, min_width?)` + `choose_photo(index)`** —
  `find_photo` returns a **shortlist** of candidates (provider fallback order
  Pexels → Pixabay → Wikimedia; unkeyed providers skipped) as the tool result
  the model sees. The model then calls `choose_photo` to pick one — or re-calls
  `find_photo` with a refined query. Nothing is picked deterministically by the
  pipeline and there is no generic fallback query pool: a search that finds
  nothing simply reports "no results". Downloads go through the existing SSRF
  guard (`check_image_url`) with a size cap and a descriptive User-Agent.
  Pixabay responses are cached 24h in-process (ToS).
- **`illustrate(style: anthropic|open-peeps|open-doodles, theme, ground)`** —
  the unified illustration director. `anthropic` routes to the procedural SVG
  generator; the two kit styles compose vendored CC0 SVGs from
  `backend/data/illustrations/{open-peeps,open-doodles}` and **recolor every
  hex fill/stroke to a brand gray token by luminance** (ink/mid/light/paper)
  via `var(--color-*)`, so output is verifier-safe and ground-adaptive.

Pipeline wiring (multi-turn function-calling via `call_llm_tool_loop`):

- **Template auto-fill** (template renderer): a template with exactly one
  empty image slot and no user media runs a **neutral** photo director that
  decides whether a photo genuinely helps (it may decline), searches via
  `find_photo`, and picks via `choose_photo`; `{{ illustration }}` slots run a
  neutral illustration director that may decline. Results are cached once per
  post in a shared per-post cache (`app/agents/orchestrator/post_cache.py`)
  because each per-format branch runs on a deep-copied state and cannot share
  `state`.
- **Designer node**: the designer's media director binds all three tools once
  per post and decides whether media helps at all; a chosen photo is appended
  to `state["images"]` (so the existing `data-image-key` render path embeds it)
  and an illustration is injected via a `data-illustration` marker after
  generation.
- Media is never forced: the director prompts are neutral ("add media only if
  it genuinely strengthens the post"), and a declined/failed media call leaves
  the slot empty (templates guard with `{% if has_image %}` /
  `{% if illustration %}`).
- Photos render grayscale via a guard CSS `filter: grayscale(1) contrast(1.05)`
  and carry an on-image attribution caption (see ADR-0017). Attribution is
  persisted on the task result as `media_credits`.

## Consequences

- Photos and hand-drawn figures now appear automatically on otherwise
  text-only template posts, preserving the monochrome brand.
- Wikimedia (keyless) works out of the box; Pexels/Pixabay activate when their
  keys are set. Missing keys → graceful "no media" fallback.
- Extra LLM calls are bounded (one photo + one illustration director call per
  post, cached; per-post photo cap).
- Hand-drawn output depends on vendored CC0 assets (~6 MB committed); keeping
  them current is a re-run of `backend/scripts/fetch_illustration_kits.py`.
