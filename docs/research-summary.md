# Research Summary

Validated on March 9, 2026.

This summary records why the current architecture is structured this way.

## 1) Template Format Choice

Decision:

- use standard `.html` templates

Why:

- universal tooling support
- no proprietary template parser required
- easy for non-TS contributors to edit

References:

- https://developer.mozilla.org/en-US/docs/Web/HTML
- https://html.spec.whatwg.org/

## 2) Build-Time Asset Embedding

Decision:

- compile config + template HTML + CSS into generated runtime JSON

Why:

- Cloudflare Worker runtime should be deterministic
- avoids runtime filesystem dependencies
- catches template/config errors during build, not at request time

References:

- https://developers.cloudflare.com/workers/
- https://developers.cloudflare.com/workers/runtime-apis/nodejs/

## 3) Template-Driven Content Contract

Decision:

- derive required slot keys from selected templates (`{{SLOT:key}}`)

Why:

- keeps LLM output contract coupled to real template requirements
- enables frequent template changes without rewriting schema by hand
- removes dependence on fixed archetype/slot-schema taxonomies

## 4) Single CSS Design System

Decision:

- keep design tokens and semantic classes in one stylesheet: `src/styles/template.css`

Why:

- central visual control
- easier maintenance and theming
- avoids style spread across YAML and TS

## 5) Dynamic Template Selection

Decision:

- LLM selects template IDs from current registry candidates per format

Why:

- template set is not static
- selection remains adaptive as new templates are added
- explicit request `templateIds` still allows deterministic overrides

## 6) Platform Stack

Ghost Content API:

- source content ingestion for `/generate` and webhook flow
- https://docs.ghost.org/content-api/posts

Workers AI:

- JSON-schema-constrained generation
- template assignment planning
- optional image prompt/model generation
- https://developers.cloudflare.com/workers-ai/features/json-mode/

Browser Rendering:

- deterministic HTML -> PNG screenshot pipeline
- https://developers.cloudflare.com/browser-rendering/get-started/screenshots/

R2:

- generated asset storage and serving
- https://developers.cloudflare.com/r2/api/workers/workers-api-reference/

## 7) Practical Outcome

The system can evolve primarily by editing:

- templates (`templates/*.html`)
- design tokens/classes (`src/styles/template.css`)
- config (`config/pipeline/*.yaml`)

Core runtime logic remains stable while content and visual output evolve quickly.

## 8) Ghost Webhook Trigger Compatibility

Decision:

- support Ghost-native webhook signatures (`x-ghost-signature`) for `POST /webhook/ghost`
- keep legacy token mode (`x-webhook-token`) for manual callers

Why:

- Ghost webhooks are standard HTTP POST requests, so Cloudflare Workers can receive them directly via the `fetch` handler
- Ghost includes webhook secret signing in `X-Ghost-Signature` using HMAC-SHA256 over `rawBody + timestamp`
- webhook payloads include `post.current.*`, which is enough to resolve slug and trigger generation

References:

- https://docs.ghost.org/webhooks
- https://docs.ghost.org/admin-api/webhooks/creating-a-webhook
- https://developers.cloudflare.com/workers/runtime-apis/handlers/fetch/
- https://github.com/TryGhost/Ghost/blob/main/ghost/core/core/server/services/webhooks/webhook-trigger.js
- https://github.com/TryGhost/Ghost/blob/main/ghost/core/test/e2e-webhooks/__snapshots__/posts.test.js.snap

## 9) R2 Binding and Key Shape

Decision:

- keep one R2 binding (`OUTPUT_BUCKET`) in Wrangler config
- reduce folder sprawl by using filename suffixes for campaign/variant uniqueness

Why:

- runtime only uses one bucket binding
- uniqueness can be preserved without per-post nested folders

References:

- https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- https://developers.cloudflare.com/workers/wrangler/configuration/
