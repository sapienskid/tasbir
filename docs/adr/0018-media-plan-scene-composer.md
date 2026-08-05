# ADR-0018 — Per-Slide Media Plan + Unified Illustration (procedural + DiceBear)

- Status: accepted (amended 2026-08-05 — Scene Composer removed)
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
- **Highlights by Outdraw** — CC0, 100+ hand-drawn SVG marks. Originally
  adopted as the hand-drawn accent layer; later **removed** with the Scene
  Composer (see below).
- **Lucide** — ISC, 1,756 consistent stroke icons. Originally adopted as the
  content-mapped motif library; later **removed** with the Scene Composer.
- **Anthropic-style procedural** — the clean three-layer abstract system
  (accent field + organic carrier blob + naive gestural linework). Pure
  deterministic SVG, monochrome-safe. **Adopted** as the default engine.
- **DiceBear curated styles** — offline, per-seed deterministic avatars,
  recolored to brand tokens. **Adopted** for human/robot posts only.

## Decision

### 1. Per-slide media plan (one LLM session per post)

`app/services/media_plan.py`: a multi-turn tool-calling session
(`call_llm_tool_loop`, bounded 16 turns) produces a **structured plan**
`{target: {kind: photo|illustration|none, style, theme}}` for every
slide/format. The plan is cached once per post (`post_cached("media_plan")`),
skipped for slides already filled by a user image, and executed in parallel by
the per-format branches.

- **Photo** → `execute_slide_photo` (search + LLM pick + SSRF-guarded download)
- **Illustration** → `execute_slide_illustration` (offline)
- **None** → slide stays clean

### 2. Two illustration engines (Scene Composer REMOVED)

The `illustrate` tool exposes `style ∈ {procedural} ∪ {open-peeps, lorelei,
notionists, bottts, blobs, initials, shapes, waves, landscape}`:

- **`procedural`** (default) — `app/services/illustration.py`: a single clean
  organic mark from a catalog of ~35 genuinely distinct archetypes. Every
  composition is a pure function of seed + theme; the post seed is threaded
  into **every element's wobble** so the same theme across different posts
  still renders different figures. Every figure is **auto-fit into a safe
  inner frame** (uniform scale + center) so it can never clip out of its slot
  box or paint over the copy.
- **curated DiceBear** — humans (open-peeps, lorelei, notionists), a robot
  (bottts), Swiss-safe abstract (blobs, initials, shapes, waves), and a
  landscape; recolored to `var(--color-*)`. Used only for people/robot posts.

The old **Scene Composer** (`composer.py` + Lucide motifs + Highlights kit)
was **removed** after a quality review: its scattered-icon output read as
amateur clip-art, and three overlapping engines produced inconsistent figures.
The vendored Lucide icons (1,756 files) and Highlights kit were deleted from
the repo. DiceBear was pruned from 25 to 9 styles (see `peep_styles.py`).

### 3. Design-system-following color

Every composed element resolves through `var(--color-*)` tokens (ground
adaptive). Editing a design token in the Studio recolors every figure with
zero code change.

### 4. Style selection precedence

`POST /generate` gains `illustration_style`; the design system gains a
`style.illustration_style` default (DB-backed). Precedence: **API override →
media-plan LLM pick → DS default → `procedural`**.

### 5. Content summary

The Strategist's typed brief gains `content_summary` (key themes + searchable
keywords, ~150 words) so the media plan can build content-derived queries.
No extra LLM call.

### 6. Big numeral = slide number

`build_template_context` sets `loop_index = slide_index` on carousel slides;
single posts keep the seeded editorial index.

### 7. User-image auto-distribution

The graph distributes user images `image i → slide i` (wrapping) into
`_slide_images`; each branch embeds only its own slide's image. Images with
`placement: "background"` route the slide to a cover/background template
(e.g. `square-cover-bg`) automatically.

### 8. Duplicate-media hard QC

`_run_sequence_check` fingerprints embedded base64 media per slide; the same
media on 2+ slides is a hard issue.

## Consequences

- Carousel slides now get distinct, content-derived media.
- Illustrations are clean editorial marks (procedural abstract or a single
  DiceBear figure), never scattered icon collages.
- Figures are guaranteed in-slot (safe-frame auto-fit) and vary per post.
- The `illustrate` tool returns **structural feedback** (archetype, element
  count, bounding box, safe-frame compliance) so the media director iterates
  to a distinct, non-overlapping figure instead of blind-guessing.
- Zero API cost preserved: one planning session per post; all illustration
  assets are offline.
- Repo got smaller: Lucide + Highlights assets deleted (~1.7 MiB removed).
- ADR-0016's "one media decision per post" model is superseded for slides;
  the curated DiceBear allowlist is reduced to the 9 Swiss-safe styles.
