# Glossary — Tasbir design system

Terms used across the config, prompts, and code. Sorted alphabetically.

## A
**Artifact** — A generated output file (`.html` or `.png`) for one format,
stored under `data/output/{task_id}/`. Delivered once over HTTP and deleted
after delivery (see *One-time download*).

## B
**Body voice** — See *Serif voice*.

## D
**Display voice** — The signature display typeface (Space Grotesk,
`var(--font-display)`) used only for the headline and the footer wordmark.
It makes posts recognizable.

## G
**Ground** — The post's background state. Only two exist: **white**
(`--color-bg`) and **black** (`--color-bg-inverted`). Never both on one post.

## K
**Kicker** — The small tracked-uppercase category label above the headline
(e.g. WRITING, PROJECT, NOTE).

## M
**Measure** — The maximum width of a body/subhead text column (~600px at
1080px canvas, scaled by width). A proper measure keeps lines readable and
reads as premium editorial.

**Metadata style** — 20px Inter, weight 500, tracking +0.08em, uppercase,
secondary gray. Used for the @handle and timestamps.

## O
**One-time download** — An opt-in delivery mode: `GET
/tasks/{id}/files/{filename}?consume=true` streams the file and then deletes
it. By default files persist until the retention sweep deletes the task's
output directory.

## P
**Per-family weights** — The weight limit applied per typeface: Space Grotesk
500+700, Source Serif 4 400, Inter 500. Three families may therefore use up
to five distinct weights total, but no single face exceeds two.

## R
**Re-render** — Rendering an operator-edited HTML document without re-running
the designer LLM: sanitize, re-inject tokens/fonts/KaTeX, render to PNG, and
run the deterministic + overflow checks. The vision audit runs only on
demand (`?audit=true`).

**Rate limit** — A Redis token bucket per API key (default 30 req/min) that
rejects excess requests with 429, protecting the LLM free-tier quota.

## S
**SSRF guard** — Validation applied to every outbound image fetch: http/https
only, loopback/link-local/metadata blocked, LAN (RFC1918/ULA) allowed, size
and redirect caps enforced.

**Serif voice** — The editorial text typeface (Source Serif 4,
`var(--font-serif)`) that carries the subhead and body copy. Reading serif at
28px gives the long-form text its literary, premium-editorial quality.

## T
**TTL sweep** — The hourly Celery beat task that deletes output directories
and task rows older than `OUTPUT_TTL_HOURS` (default 24h), bounding disk and
DB growth.

**Tasbir Studio** — The React + Vite + shadcn/ui SPA served same-origin by
FastAPI: task list, Monaco HTML editor, PNG preview, QC report, downloads,
and delete.

**Type role** — A named element in the type scale (category, headline,
subhead, body, metadata) with a fixed family, size, weight, tracking, and
leading. Roles, not arbitrary styles, define every text element.

## W
**Wordmark** — The footer name "SABIN POKHAREL" rendered in the display face
(Space Grotesk, ~24px, tight tracking) as a signature logotype. Typography is
the brand's only mark.
