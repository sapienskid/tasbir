# Blog and newsletter covers

Open **Covers** in Studio, choose a design system, and enter an article title,
excerpt, or visual direction. Pick a composition or let the article's keywords
select a family. Preview a procedural drawing, then generate 1–4 variations.
Every variation can be downloaded as PNG, standalone SVG, or HTML; **Download
all** bundles the artifacts into a ZIP. Covers also appear in Tasks.

Canvas presets are 1600×900 (blog/newsletter), 1200×630 (Open Graph), and
1080×1080 (square). The API accepts dimensions from 256 to 2400 pixels per axis.
Artwork contains no titles, categories, handles, or footer. Add typography in
your publishing tool if needed.

## Artwork engines

**Procedural drawing** runs locally with no model calls. The shared illustration
engine includes scientific curves, hand/plant/object compositions, and all 15
motifs from the supplied procedural program:

| Motif | Composition |
| --- | --- |
| `field-flow` | Noise-driven streamlines |
| `field-burst` | Radial rays and satellite dots |
| `field-tiles` | Bauhaus geometric tiles |
| `field-blobs` | Organic shapes and offset ink outlines |
| `field-orbits` | Wobbly rings and planets |
| `field-waves` | Layered noise ridges and a sun |
| `field-hatch` | Clipped hatching in organic shapes |
| `field-stipple` | Sphere shaded by stipple density |
| `field-mesh` | Noise-warped grid with a lens distortion |
| `field-contour` | Marching-squares topographic contours |
| `field-nodes` | Clustered network with a highlighted path |
| `field-cubes` | Isometric blocks from a noise heightmap |
| `field-scribble` | Continuous looping pen line |
| `field-halftone` | Hexagonal halftone field |
| `field-phyllo` | Sunflower phyllotaxis with spiral accents |

Field motifs intentionally reach the canvas edge. Isolated illustrations use
the existing safe-frame fitting. All are also available to the social pipeline
through the `illustrate` tool's `theme` parameter.

The drawing seed reproduces geometry at the same size and settings. Preview
freezes a seed so the first generated study matches the preview. Auto mode
uses keyword families, not an LLM understanding of arbitrary visual directions;
select a specific composition for precise control. New batches can use the same
settings with a fresh seed.

**AI artwork** calls Cloudflare Workers AI's
`@cf/black-forest-labs/flux-1-schnell`. It uses the existing resolved Cloudflare
account/token configuration and Gateway ID header. The token must have Workers
AI inference access; credential presence alone does not prove access or quota.
Each variation makes one inference call, with no automatic provider retry.
Failed variants can be retried explicitly. Seeds reproduce procedural drawings;
AI generation is not guaranteed reproducible. Review AI artwork for accidental
lettering before publishing.

## Palette and texture

Both engines use the selected DB-backed design system. The supplied program's
hardcoded palettes and lime highlight are replaced by semantic background, ink,
secondary, border, and optional accent tokens. No colors from example prompts
are installed.

The default design system now seeds lime (`#C6F432`) as `--color-accent`, with
white/black grounds and grayscale type. It is used for focal artwork fills and
highlights, not small text. Other design systems keep their own token palettes.

Procedural SVG uses CSS variables directly. AI receives grayscale art direction,
never brand token values. An SVG luminance filter maps the returned raster into
the selected system's colors before PNG rendering. Antialiasing and print grain
can create blended edge shades. No unrestricted source raster is exported.
AI SVG files embed a raster; procedural SVG files remain vector drawings.

## Queue, rendering, and retries

`POST /api/covers` creates a normal `GenerationTask` with
`source_data.mode="cover"` and queues `app.tasks.covers.cover_task`. The social
strategist/copywriter/designer pipeline is skipped. Restart the API and Celery
worker after installing this change so the route and task are registered.
PNG export uses the existing Playwright service.

Artifacts live under `data/output/{task_id}/cover-N.{svg,html,png}` and follow
normal task retention. A failed PNG render retains SVG/HTML. Retrying reuses
saved HTML and completed PNG variants, avoiding another inference call when
only rendering failed. A failure before artwork is saved requires fresh
inference. Rendered status indicates artifact creation, not a vision audit.

API routes require the normal API key. `GET /api/covers/meta` publishes motifs,
canvas presets, and whether Cloudflare credentials are present.
`POST /api/covers/preview` is procedural-only and uses the interactive rate tier.
Downloads use the normal task file/archive endpoints.

```json
{
  "design_system_id": "default",
  "title": "The limits of computation",
  "engine": "procedural",
  "motif": "field-contour",
  "ground": "black",
  "texture": "print",
  "width": 1600,
  "height": 900,
  "variations": 3,
  "seed": "limits-07"
}
```

## CLI

Run from `backend/` with the normal Tasbir environment and a seeded database:

```bash
.venv/bin/python procgen.py -m burst -s 7 --grain --png
.venv/bin/python procgen.py -m contour -t "The limits" --size 1200x630
.venv/bin/python procgen.py -n 12 -d default --ground black -o covers/study
```

The CLI accepts the original motif names as aliases for `field-*`, as well as
the full cover composition catalog. `--title` hashes the normalized title into
a stable seed; batches increment it. `--design-system` replaces the original
palette argument. SVG drawing math uses only the Python standard library;
the adapter loads the palette from Tasbir's DB. Optional `--png` uses the
configured Playwright renderer, so `rsvg-convert` is not required.
