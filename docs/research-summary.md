# Research Summary

Validated on March 4, 2026.

This document records the design decisions behind the current architecture.

## 1) Template File Format: `.html` vs `htmlx`

Decision:

- use standard `.html` files

Reasoning:

- `.html` is universal and tool-friendly
- no special loader is required
- `htmlx` is not a web-standard template format
- if the intention is `htmx`, it still uses regular `.html`

References:

- https://developer.mozilla.org/en-US/docs/Web/HTML
- https://html.spec.whatwg.org/
- https://htmx.org/docs/

## 2) Configuration Strategy

Decision:

- maintain one composed YAML control plane via `config/pipeline.config.yaml` with focused fragments in `config/pipeline/*.yaml`

Reasoning:

- human-readable, nested structure fits this domain
- easy to review in pull requests
- keeps style/archetype/font/template policies centralized while reducing single-file complexity

Reference:

- https://yaml.org/spec/1.2.2/

## 3) Worker Runtime Determinism

Decision:

- compile YAML + HTML into TypeScript at build time

Reasoning:

- Cloudflare Worker runtime should not depend on local filesystem reads
- generated asset module makes deploy behavior deterministic
- validation failures happen at build time, not after deploy

References:

- https://developers.cloudflare.com/workers/
- https://developers.cloudflare.com/workers/runtime-apis/nodejs/

## 4) Stack Choices Retained

Ghost Content API:

- source-of-truth blog content ingestion
- https://docs.ghost.org/content-api/posts
- https://docs.ghost.org/content-api/parameters

Workers AI:

- structured JSON output for captions/slots/style/archetype/font
- image generation fallback
- https://developers.cloudflare.com/workers-ai/features/json-mode/
- https://developers.cloudflare.com/workers-ai/models/gpt-oss-120b/
- https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/

Browser Rendering:

- deterministic HTML -> PNG capture
- https://developers.cloudflare.com/browser-rendering/get-started/screenshots/

R2:

- output asset storage and optional public URL serving
- https://developers.cloudflare.com/r2/api/workers/workers-api-reference/

## 5) Outcome

The resulting architecture supports broad template expansion with minimal code changes:

- add/edit HTML templates
- register behavior in YAML
- rebuild assets
- render through one generic runtime pipeline
