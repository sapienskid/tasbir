# ADR-0018 — Per-Slide Media Plan + Unified Scene Composer

- Status: accepted
- Date: 2026-08-04
- Related: ADR-0016 (media tools), ADR-0017 (attribution policy)

## Context

The v3 media layer treated media as **one-per-post**: the photo director ran
once (`post_cached(task_id, "photo")`) and every carousel slide — and every
format of the same post — embedded the **same photo**. Observed defects:

1. **Duplicate media across slides** — every frame of a carousel showed the
   identical image.
2. **Content-blind media** — the director received only title + headline +
   category, so search queries and illustration subjects bore little relation
   to the actual body of the post.
3. **Illustrations were not content-relevant** — DiceBear avatars (a literal
   person-face) and abstract procedural blobs both failed the "editorial
   meaning" test; neither composed a subject.
4. **Template numerals were meaningless** — `index-numeral`,
   `portrait-index`, and `story-costs` rendered a seeded random number
   (1–27) instead of the slide number.

We needed per-slide, content-derived media; a content-mapped illustration
engine; and slide-accurate numerals — all while keeping the zero-API-cost
target and the strict Swiss monochrome rules (no hex, no emoji, only
`var(--color-*)`).

## Research

- **EnigmaKit** — a Figma community file (~600 hand-drawn elements); no
  downloadable SVG source. **Rejected**.
- **Highlights by Outdraw** — CC0, 100+ hand-drawn SVG marks (arrows,
  underlines, sprinkles, loops, spirals, doodles, blobs, donuts, lines).
  Single-path `fill="black"` + `fill="none"` + one accent `#4633FF`; no
  gradients/defs. Recolors cleanly through the existing luminance mapper.
  **Adopted** as the hand-drawn accent layer.
- **Lucide** — ISC, 1,756 consistent stroke icons (24×24, `fill="none"`
  `stroke="currentColor"`), each shipping `<name>.json` with tags+categories.
  **Adopted** as the content-mapped motif library. (Tabler/Phosphor — MIT —
  are interchangeable if more coverage is ever wanted.)
- **unDraw / Storyset** — custom license / freemium scenes with gradients and
  color; conflict with `gradients: false`. **Rejected**.

## Decision

### 1. Per-slide media plan (one LLM session per post)

New `app/services/media_plan.py`: a multi-turn tool-calling session
(`call_llm_tool_loop`, bounded ~12 turns) produces a **structured plan**
`{target: {kind: photo|illustration|none, query, style, archetype,
motif_names, highlights, theme}}` for every slide/format. The plan is cached
once per post (`post_cached("media_plan")`), skipped for slides already
filled by a user image, and executed in parallel by the per-format branches.

- **Photo** → `execute_slide_photo` (search + LLM pick + SSRF-guarded download)
- **Illustration** → `execute_slide_illustration` (offline scene compose)
- **None** → slide stays clean

### 2. Unified Scene Composer

New `app/services/tools/composer.py`: a pure deterministic function
`compose_scene(seed, ground, archetype, hero, motif_names, highlights, style,
theme, category)` that lays out up to five element sources under a named
**composition archetype** (22 shipped):

- custom category **hero** SVGs (`illustrations/heroes/`: fountain-pen,
  wrench-gear, frame, spark, robot)
- **DiceBear figures** (kept for humans/robots only)
- **Lucide motifs** rendered with `stroke: currentColor` + `color:
  var(--ill-ink)`
- **Highlights marks** recolored through the design system tokens
- procedural **geometry** (hairlines, wobble lines, blobs, dot grids)

The `illustrate` tool now exposes `style ∈ {compose, procedural} ∪
{open-peeps, lorelei, notionists, bottts, blobs, initials, shapes, waves,
landscape}` — DiceBear was **pruned from 25 to 9** styles (humans + robots +
Swiss-safe abstract + landscape); everything else removed from the registry.

### 3. Design-system-following color

Every composed element resolves through the ground-adaptive `--ill-*` tokens
(which the `.figure` wrapper derives from `--color-*`). Editing a design
token in the Studio recolors every figure with zero code change. The
`#4633FF` Highlights accent maps to `--ill-mid` (strict monochrome).

### 4. Style selection precedence

`POST /generate` gains `illustration_style`; the design system gains a
`style.illustration_style` default (DB-backed). Precedence: **API override →
media-plan LLM pick → DS default → `compose`**.

### 5. Content summary

The Strategist's typed brief gains `content_summary` (key themes + searchable
keywords, ~150 words) so the media plan can build content-derived queries and
motif choices. No extra LLM call.

### 6. Big numeral = slide number

`build_template_context` sets `loop_index = slide_index` on carousel slides;
single posts keep the seeded editorial index. `index-numeral`,
`portrait-index`, and `story-costs` now show the real slide position.

### 7. User-image auto-distribution

The graph distributes user images `image i → slide i` (wrapping) into
`_slide_images`; each branch embeds only its own slide's image.

### 8. Duplicate-media hard QC

`_run_sequence_check` fingerprints embedded base64 media per slide; the same
media on 2+ slides is a hard issue. A bounded retry forces the duplicate
slides to `kind: none` (no extra LLM planning call) and re-runs those
branches.

## Consequences

- Carousel slides now get distinct, content-derived media instead of a
  repeated photo.
- Illustrations are content-mapped scenes (hero + motifs + hand-drawn marks)
  rather than avatars or abstract blobs.
- Composed figures follow the active design system automatically.
- Zero API cost preserved: one planning session per post; all illustration
  assets are offline.
- ~1.7 MiB of git size added (Lucide 1,756 SVGs + Highlights 117 SVGs +
  catalog) — a one-time, offline-forever cost.
- ADR-0016's "one media decision per post" model is superseded for slides;
  the curated DiceBear allowlist is reduced to the 9 Swiss-safe styles.
