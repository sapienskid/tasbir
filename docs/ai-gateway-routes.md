# AI Gateway setup — routes for Tasbir

100% of LLM traffic goes through the Gateway compat endpoint
(`gateway.ai.cloudflare.com/.../compat/chat/completions`, OpenAI chat shape).
There are no direct provider calls anywhere — no LangChain, no OpenRouter.
`GEMINI_API_KEY` is only ever sent as the Gateway's BYOK credential
(`x-goog-api-key` is not even needed: the Gateway holds the key); nothing
calls `googleapis.com` directly. If every Gateway attempt fails the call
raises (fail-loud — no silent fallback that would bypass quotas/logging).

The pipeline calls three dynamic routes. Until they exist, generation
transparently uses the provider-specific Google path (same models, same
Gateway logging) — creating the routes only moves failover server-side
(no deploy to change models later).

## 0. Prerequisites

- Gateway id `tasbir` (code default `CF_GATEWAY_ID`; any id works if the
  env var matches).
- Google AI Studio key stored (BYOK) or available via Unified Billing.
- Gateway credits are NOT needed: every generation path uses the
  `google-ai-studio` provider slug (BYOK, free tier), and Clef/Clef-flash
  bill Neurons (free daily allocation). Do NOT use the `google/` slug —
  probed live, it bills Gateway credits (402) instead of the free tier.

## 1. Model budgets (free tier) — read this before routing

Google AI Studio free-tier limits per model, and they decide everything:

| Model | RPM | TPM | RPD | JSON contract |
|---|---|---|---|---|
| Gemma 4 31B | 30 | **16K** | 14.4K | ✗ echoes the prompt |
| Gemma 4 26B A4B | 30 | **16K** | 14.4K | ✗ echoes the prompt |
| Gemini 3.1 Flash Lite | 15 | 250K | 500 | ✓ |
| Gemini 3.5 Flash Lite | 15 | 250K | 500 | ✓ |

Two consequences:

1. **Gemma's 16K TPM is the binding constraint.** A 5,000-word article is
   ~7.7K tokens — one call eats ~48% of the whole minute budget. Long
   content is therefore *read by Gemini and compressed* before any Gemma
   call (`services/content_reduce.py`); Gemma only ever sees the brief.
2. **Gemma must not serve JSON-only agents.** Verified live: Gemma returns
   `*   Input: ...` prose instead of the object. JSON-only roles
   (strategist, planner, copywriter) pin to `gemini-3.1-flash-lite`, and
   `pick_model(..., require_json=True)` skips Gemma entirely.

So: **Gemini reads, Gemma writes prose, Clef judges.** The `model_quota`
module reserves tokens against these windows before each call so a burst of
parallel format branches cannot 429 mid-pipeline.

## 2. Create the three routes

Dashboard → AI Gateway → gateway `tasbir` → Dynamic Routes → Add Route,
repeat for each row. Provider for every Model node: **Google AI Studio**.

| Route | Node 1 (primary) | Node 2 | Node 3 | Final net (Workers AI, Neuron-billed) | Serves |
|---|---|---|---|---|---|
| `tasbir-fast` | `gemma-4-26b-a4b-it` (prose only) | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `workers-ai/@cf/ibm-granite/granite-4.0-h-micro` ($0.017/M, strong instruction-following) | strategist\*, planner\*, brand_tokens, brand_campaigns |
| `tasbir-creative` | `gemini-3.1-flash-lite` (JSON-capable) | `gemma-4-31b-it` | `gemma-4-26b-a4b-it` | `workers-ai/@cf/openai/gpt-oss-120b` (128k ctx, strongest free creative reasoning) | copywriter\*, designer, template_author, editor_chat |
| `tasbir-vision` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemma-4-31b-it` | `workers-ai/@cf/mistralai/mistral-small-3.1-24b-instruct` (vision-capable, 128k ctx) | verifier, template_vision, brand_vision (all vision-capable) |

\* JSON-only roles never *rely* on the route's primary: they pass
`model_override=gemini-3.1-flash-lite`, which bypasses the route entirely, and
retry with an explicit output contract if the first parse fails. Gemma nodes
are therefore safe to keep for prose, but they must never be the only path to
a JSON object.

Nodes 1–3 use provider **Google AI Studio**; the final net uses provider
**Workers AI** with the `@cf/…` id verbatim. Workers AI bills in Neurons
(free 10k/day covers these volumes), so the net holds even with zero
Gateway credits.

> Scope note: none — every generation path (plain chat, tool-calling loops,
> vision audits) goes through the Gateway compat endpoint. The old direct
> Google (LangChain) and OpenRouter fallbacks are deleted; decisions were
> always Cloudflare-native (Workers AI).

### Verified live (Oct 2026)

* The **compat endpoint is the single path**. The unified REST path
  (`api.cloudflare.com/.../ai/v1/chat/completions`) was probed:
  `google-ai-studio/{model}` → 404, `google/{model}` → 402 (bills Gateway
  credits instead of the free tier). Compat + `google-ai-studio/` is 200.
* **Tools work through the Gateway** (Oct 2026): `tools` + `tool_choice`
  through both `dynamic/tasbir-fast` (served by gemini-3.1-flash-lite) and
  `google-ai-studio/gemini-3.1-flash-lite` return OpenAI-shaped `tool_calls`.
  Provider extras (`extra_content.google.thought_signature`) are dropped
  when the message is echoed back; route models may also prepend
  `<thought>` blocks, which the client strips.
* **Vision works through the Gateway** (Oct 2026): `image_url` parts
  through `dynamic/tasbir-fast` (served by gemma-4-26b-a4b-it) correctly
  described a 102KB 1080×1080 render.
* `google/{model}` returns `400 Model not found` for every model; the working
  Google slug is **`google-ai-studio/{model}`** on both the compat host and
  the unified API path. `services/llm.py` uses the working slug.
* `gemma-4-26b-a4b-it` intermittently returns **500**; `gemini-3.1-flash-lite`
  intermittently returns **503 high demand**. This is why every route needs
  its Workers AI net.
* `gemma-4-3x-it` is **not** resolvable through the chat-completions shape
  (404) but **is** reachable through the provider passthrough
  (`/google-ai-studio/v1/models/{id}:generateContent`).

Flow per route: Start → Model 1 → (on failure) Model 2 → (on failure)
Model 3 → End. Save a version, then **Deploy**.

Optional hardening (same Editor): add a Rate Limit node before the
models (fast/creative: 30 req/min; vision: 15 req/min — mirrors
`services/models.py`) and a Budget Limit node per your monthly cap,
both falling through to the next Model node.

## 2. Verify

```bash
# From backend/ with the Cloudflare env vars exported:
.venv/bin/python /tmp/opencode/cf_smoke.py
```

`route.ok: true` + a non-null `served` model means the route served.
The served model lands in the app logs (`[LLM] gateway route served by …`)
and per-agent audit rows.

## 3. Decision-model policy (code, not dashboard)

Running dev containers with these wired:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

`x-shared-env` passes `LLM_PROVIDER`, `CLOUDFLARE_ACCOUNT_ID`,
`CLOUDFLARE_AI_GATEWAY_TOKEN`, `CF_GATEWAY_ID`,
`DECISION_PROVIDER_ORDER`, `DECISION_CALIBRATION_RATE`, and
`COPY_QA_ENFORCE` into api/worker/beat, and the renderer is published on
`localhost:4000`. Both api and worker hot-reload the bind-mounted backend,
so decision/pack edits apply without a rebuild.

Text judgments run **Clef-flash first, Clef fallback** (`decision_packs.py`
— flash is the fast workhorse on free Neurons; Clef-full is the precision
second opinion). **Full Clef leads the vision packs** (`verifier-visual`,
`sequence-cohesion`, `image-relevance` — the only packs that send images).
Clef is the only decision model we run; both providers bill in Neurons, so
decisions never need Gateway credits.

> Dynamic routes cannot front decision calls: routes accept the OpenAI chat
> shape only, while decisions use the System One `ai/run` shape (`{state,
> questions}`). Decision failover lives client-side in `decide()` order,
> which is where the "decide fast, act in a loop" budget lives: one cheap
> flash call answers every gate question in parallel (~40 ms), and only the
> answer's probabilities decide the next branch.

Per-pack actions (probabilities → code, never prose):

| Pack | Action |
|---|---|
| `intake-router` | `safety_flag ≥ 0.8` → task refused with a clear error (no silent fallback). `needs_human ≥ 0.5` → `needs_review` flag on the brief. Approved-category vote adopted only when the LLM missed the taxonomy. Provider errors → no action (fail-open). |
| `copy-voice/claims/structure` + `headline-hook` | Merged into two calls (12 + 5 questions) → composite `copy_quality` score (brand 0.35 / clarity 0.25 / CTA 0.2 / value 0.2). `≥ 0.80` pass, `0.60–0.80` human review, `< 0.60` rewrite; weak hooks (`< 0.40`) flagged. Blocking (`copy_qa_blocked`) only when `COPY_QA_ENFORCE=true`; copy is never dropped. Failing claim dimensions ride into the verifier prompt as extra scrutiny. |
| `extras-check` (built per post type) | Presence Noul per filled extra + groundedness vs source. Advisory in copy QA; empty for `default` posts (no call). |
| `design-brief` | Post-HTML semantic check (headline/body/focus/craft) after deterministic gates pass. Advisory — stored in verification for calibration against the syntactic checks. |
| `media-kind` vote, `critique-actionable` | Advisory audit trail (agreement calibration). They never flip a deterministic result today — the logs tell us which pack earns enforcement next. |
| `planner-gate`, `verifier-pregate`, `sequence-cohesion` | Advisory audit trail (agreement calibration). They never flip a deterministic result today — the logs tell us which pack earns enforcement next. |
| `refine-focus` (loop driver) | On any failed gate (deterministic, overflow, contrast, vision audit) one flash call picks the single highest-leverage fix + whether it's reachable from HTML/CSS, and renders a targeted brief appended to the critique the next attempt sees. Confident + reachable → retry with a pointed brief; low confidence or unreachable → the loop **stops** instead of burning attempts. |

## 4. The loops (this is where the cost win is)

Two bounded loops are driven by decisions, not by blind replay:

1. **Design loop** (`verifier.max_retries`, default 3): render → gate → Clef
   picks the fix → next attempt reads the targeted brief → repeat, or stop
   when Clef says no reachable fix exists. Each turn costs one ~40 ms flash
   call instead of another round of "do better" prompting.
2. **Copy loop** (`copywriter.qa_max_rounds`, default 1; 0 disables): write →
   QA packs score it → the failing dimensions become an explicit revision
   brief → one rewrite pass → re-score. The revised copy is what ships.

Tuning: both knobs are Studio-editable under Settings (seed-once defaults
above); `COPY_QA_ENFORCE` additionally marks `rewrite` verdicts as
do-not-publish in the task result.

## 5. Question-writing rules (when adding a pack)

One judgment per question; positive framing (high = yes); Choice 2–255
options + `other` escape hatch; Score 2–10 ordered levels, lowest first;
Noul decisiveness = distance from 0.5. Never ask for counts, dates, hex
codes, or double negatives — judge in the model, compute in code.
Version questions + criteria + thresholds together (`version` field) and
replay the labeled set on any change.
