# ADR-0017 — Media Attribution Policy (photos & hand-drawn kits)

- Status: accepted
- Date: 2026-08-03
- Related: ADR-0016, ADR-0009

## Context

Stock photos carry licensing obligations that vary by provider:

- **Unsplash** requires prominent photographer attribution and hotlinking.
- **Pexels** asks for a prominent link to Pexels and to credit photographers
  "when possible".
- **Pixabay** asks that the source be shown wherever search results are
  displayed.
- **Wikimedia Commons** images are typically CC-BY / CC-BY-SA / CC0. CC-BY and
  CC-BY-SA **legally require** attribution in the output.

The pipeline's footer is strictly two brand handles; there is no natural place
for a photo credit, and a clean shareable PNG should still be legally compliant.

## Decision

Render an **on-image attribution caption** for every photo placed by the media
tools:

- A small tracked-uppercase caption overlays the photo's bottom-right corner
  (e.g. "Photo by Daria on Pexels", "Wikimedia Commons · author · CC BY-SA 4.0").
- The caption uses the brand's metadata type scale and `var(--color-*)` tokens,
  so it passes the verifier and reads as part of the system.
- Provider, photographer, license, and the full credit string are always
  persisted on the task result as `media_credits` (shown in the Studio).

Hand-drawn kits (Open Peeps, Open Doodles) are CC0 public domain and need no
attribution; they are vendored into the repo (ADR-0016).

Unsplash remains excluded (hotlinking conflicts with the base64 pipeline and
its 50 req/hr demo tier is too small); if it is ever added it must follow the
same caption rule.

## Consequences

- Outputs stay license-compliant for Wikimedia/CC content without a separate
  footer redesign.
- The caption adds a small element inside photo slots; templates with
  constrained slots must keep the overlay inside the image bounds (the embed
  replaces only the `<img>`, preserving the template's own slot sizing).
