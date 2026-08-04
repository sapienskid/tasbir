# ADR-0016 — LLM-Callable Media Tools (photos + DiceBear illustrations)

- Status: accepted
- Date: 2026-08-03 (updated 2026-08-04 — DiceBear part-based engine)
- Related: ADR-0009 (SSRF), ADR-0015 (config in DB), ADR-0017 (attribution policy)

## Context

The illustration generator (ADR: Anthropic-style procedural SVG) proved the
tool pattern, but a strict procedural generator can't deliver real photos or
the hand-drawn people/scenes users expect from the "editorial" brand. We
needed stock photos and CC0 hand-drawn illustration kits, while keeping three
invariants:

1. **Monochrome brand** — "no hue, ever". Photos and illustrations must render
   grayscale.
2. **Verifier-safe output** — no raw hex anywhere in the final HTML; only
   `var(--color-*)`.
3. **Zero API cost target** — free tiers only, degrade gracefully without keys.

Research findings: Pixabay requires downloading (no hotlinking) and 24h search
caching; Pexels offers 200 req/hr free with an exactly-1200×627 landscape crop;
Unsplash requires hotlinking (conflicts with our base64 pipeline) and has a
50/hr demo tier — rejected as primary. Wikimedia Commons is keyless but
requires a descriptive User-Agent and honors CC licenses that mandate
attribution.

**Illustration sourcing evolution.** v1 vendored Pablo Stanley's **Open Peeps /
Open Doodles** whole-figure CC0 SVGs and *selected* one per post by seed hash.
That was selection from a fixed set, not creation. Research surfaced **DiceBear**
— an open-source (MIT lib / CC0 art) part-based avatar engine with official
**Python bindings** (`dicebear-core` + `dicebear-styles`, pure Python, fully
offline: style definitions ship inside the wheel). A figure is composed from
independent parts (hair, face, facial hair, accessories…) on a shared canvas,
deterministically from a seed → ~231M unique combos, and every part is
**pinnable** (`facialHairVariant=moustache3&facialHairProbability=100` →
exactly that part in the output).

**IRA Design** (Creative Tim, MIT) was evaluated as an alternative scene
library: it ships whole pre-drawn characters/objects (no part composition), has
no Python package, and its gradient assets conflict with the Swiss
`gradients: false` rule — rejected.

## Decision

Expose two LLM function-calling tools behind a small tool registry
(`app/services/tools/`):

- **`find_photo(query, orientation?, min_width?)` + `choose_photo(index)`** —
  unchanged. `find_photo` returns a **shortlist** of candidates (provider
  fallback Pexels → Pixabay → Wikimedia; unkeyed providers skipped); the model
  calls `choose_photo` to pick or refines the query. Downloads go through the
  SSRF guard with a size cap. Pixabay responses cached 24h (ToS).
- **`illustrate(style, theme, ground, facial_hair?, hair?, expression?,
  accessory?)`** — the unified illustration director.
  - `style = "anthropic"` → the existing procedural Anthropic-style SVG
    generator.
  - `style` = any of a **curated allowlist** of DiceBear styles (see below) →
    `compose_peep()` renders via the Python `dicebear-core`, strips the RDF
    `<metadata>`/comment banner, **recolors every hex + named (`black`/`white`)
    fill/stroke to a brand gray token by luminance** (ink/mid/light/paper) via
    `var(--color-*)`, rewrites part ids to a `z-` prefix (so `#face-…` id refs
    can't be read as raw hex), and wraps in a ground-adaptive `.figure`.
    Mask fills are recolored to the ground-stable `--ill-light`/`--ill-mid`
    tokens so luminance masks survive both grounds.
  - Part pins are only honored for people/robot styles (validated against the
    live `OptionsDescriptor`); abstract styles ignore them gracefully.

### Curated allowlist (25 styles, all CC0 / free-for-commercial)

- **People (7):** `open-peeps`, `lorelei`, `lorelei-neutral`, `notionists`,
  `notionists-neutral`, `bottts`, `bottts-neutral`
- **Creatures (2):** `critters`, `sprouts`
- **Faces (4):** `clay`, `moods`, `pixelbot`, `initial-face`
- **Abstract (11):** `blobs`, `rings`, `stripes`, `triangles`, `waves`,
  `shapes`, `squircles`, `shape-grid`, `loops`, `disco`, `weave`
- **Landscape (1):** `landscape`

Excluded for cause: 13 **CC BY 4.0** styles (attribution-required — the
pipeline adds no credits for illustrations): `adventurer*`, `big-ears*`,
`big-smile`, `croodles*`, `dylan`, `glyphs`, `micah`, `miniavs`, `personas`,
`toon-head`; `initials` (renders text); `fun-emoji` (emoji-adjacent + CC BY);
`identicon`/`pixel-art` (5×5/16×16 micro-canvases); `avataaars`,
`constellation`, `planets` (use gradients — forbidden by `gradients: false`).

The registry (`app/services/tools/peep_styles.py`) derives each style's
pinnable parts and allowed values **from the live DiceBear `OptionsDescriptor`**
at import time, so the tool schema never drifts from what a style accepts.

Pipeline wiring (multi-turn function-calling via `call_llm_tool_loop`):

- **Template auto-fill** (template renderer): a template with exactly one empty
  image slot and no user media runs a **neutral** photo director; `{{
  illustration }}` slots run a neutral illustration director. Results cached
  once per post (`app/agents/orchestrator/post_cache.py`).
- **Designer node**: the media director binds all three tools once per post;
  a chosen illustration is injected via a `data-illustration` marker.
- Media is never forced; a declined/failed call leaves the slot empty.
- Photos render grayscale with an on-image attribution caption (ADR-0017) and
  persist `media_credits` on the task result.

## Consequences

- Illustrations are now **generated** (part-based, deterministic, ~231M combos
  for people styles) rather than selected from a fixed set — and each style's
  parts can be pinned by the LLM.
- No vendored illustration assets; the `dicebear-*` wheels (≈790 KB) ship the
  definitions offline. `backend/data/illustrations/` and
  `backend/scripts/fetch_illustration_kits.py` were removed.
- Default palette is `line` (2-tone ink/paper); `mono` (4-tone) and
  `original` (DiceBear colors, preview-only) remain available as options.
- Extra LLM calls are bounded (one photo + one illustration director call per
  post, cached; per-post photo cap).
- Determinism depends on pinned `dicebear-core==10.4.0` /
  `dicebear-styles==10.3.0`; upgrade deliberately to avoid output drift.
