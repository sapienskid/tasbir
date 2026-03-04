# Research Summary (validated on March 4, 2026)

## 1) Template file format decision: `.html` vs `htmlx`

Decision: use `.html`.

Why:
- `.html` is the standard HTML document format with universal tooling/editor support.
- The HTML specification and mainstream documentation center on standard HTML documents.
- `htmlx` is not a standard web template file extension.
- If the intent was **htmx**, it is an HTML attribute-based library and still works with normal `.html` files.

Sources:
- https://developer.mozilla.org/en-US/docs/Web/HTML
- https://html.spec.whatwg.org/
- https://htmx.org/docs/

## 2) Central configuration format decision

Decision: use one YAML config file (`config/pipeline.config.yaml`) as the project control plane.

Why:
- YAML is a mature, human-editable serialization format.
- It handles nested config for brand defaults, style taxonomy, format dimensions, and template registry cleanly.

Source:
- https://yaml.org/spec/1.2.2/

## 3) Cloudflare Worker compatibility

Decision: compile YAML + template HTML into generated TypeScript at build time.

Why:
- Worker runtime should stay deterministic and avoid runtime filesystem assumptions.
- Build-time generation keeps runtime fast and makes template/config changes explicit via source control.

Sources:
- https://developers.cloudflare.com/workers/
- https://developers.cloudflare.com/workers/runtime-apis/nodejs/

## 4) Existing platform choices retained

- Ghost Content API ingestion
  - https://docs.ghost.org/content-api/posts
  - https://docs.ghost.org/content-api/parameters

- Workers AI for JSON-structured copy and image generation
  - https://developers.cloudflare.com/workers-ai/features/json-mode/
  - https://developers.cloudflare.com/workers-ai/models/gpt-oss-120b/
  - https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/

- Browser Rendering for HTML -> PNG
  - https://developers.cloudflare.com/browser-rendering/get-started/screenshots/

- R2 for output storage
  - https://developers.cloudflare.com/r2/api/workers/workers-api-reference/

## Final recommendation

Keep the Worker orchestration and Cloudflare-native stack, but make template behavior configuration-driven:
- `.html` templates in repository
- single YAML configuration authority
- build-time registry generation
- runtime template/style resolution from config + model output
