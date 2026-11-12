# Cover artwork refinement

The first cover generator varied complete motif drawings, but layering those
drawings produced disconnected collages. Changing a seed must affect the
structure of an illustration, and the preview must faithfully represent the
exported artwork.

The default generative mode now constructs connected vector subjects from
seeded geometry. Stems, leaves, vessel openings, and nested curves share
anchors and proportions. A single accent belongs to a constituent shape;
the selected design system supplies its actual color. The recipe exposes the
parts of the drawing for inspection. These are bounded procedural grammars,
not arbitrary visual understanding or a promise of unlimited distinct designs.
The existing field motifs and mathematical families remain selectable.

Studio selects a random seed when the form opens and exposes Shuffle. A
debounced preview follows changes automatically, cancels obsolete requests,
and allows export only when the displayed drawing matches the current form.
AI generation remains an explicit action. Manual Compose resolves the same
design system for both its illustration thumbnail and rendered post, and
offers a larger fitted illustration slot.

Local development uses bind mounts, polling file watchers, API reload, worker
and beat restart, and Vite hot updates. The API host port is configurable with
`TASBIR_DEV_API_PORT`; this workstation uses 8001 and Studio uses 5173. The
development renderer image has an independent tag to avoid stale production
image pins. This refinement is for local review before another deployment.

Validation covers seed reproducibility, palette substitution, SVG safety and
containment, recipe variation, preview/export equality, request cancellation,
manual composition, and template theming. Rendered contact sheets supplement
the automated checks: passing tests alone does not establish artwork quality.
