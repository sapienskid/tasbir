# AI Gateway setup — routes for Tasbir

The pipeline calls three dynamic routes when `LLM_PROVIDER=gateway`.
Until they exist, generation transparently uses the provider-specific
Google path (same models, same Gateway logging) — creating the routes
only moves failover server-side (no deploy to change models later).

## 0. Prerequisites

- Gateway id `tasbir` (code default `CF_GATEWAY_ID`; any id works if the
  env var matches).
- Google AI Studio key stored (BYOK) or available via Unified Billing.
- Gateway credits topped up if you want the `google/` compat slug and
  Jev (third-party billing). The provider-specific Google path and
  Clef/Clef-flash (Neurons) work without credits.

## 1. Create the three routes

Dashboard → AI Gateway → gateway `tasbir` → Dynamic Routes → Add Route,
repeat for each row. Provider for every Model node: **Google AI Studio**.

| Route | Node 1 (primary) | Node 2 | Node 3 | Serves |
|---|---|---|---|---|
| `tasbir-fast` | `gemma-4-26b-a4b-it` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | strategist, planner, brand_tokens, brand_campaigns |
| `tasbir-creative` | `gemma-4-31b-it` | `gemini-3.1-flash-lite` | `gemma-4-26b-a4b-it` | copywriter, designer, template_author, editor_chat |
| `tasbir-vision` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemma-4-31b-it` | verifier, template_vision, brand_vision (all vision-capable) |

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

Text judgments run **Clef-flash first, Jev fallback**
(`decision_packs.py` — flash is the fast workhorse on free Neurons;
Jev takes over automatically once credits exist). **Clef-full is
vision-only** (`verifier-visual`, `sequence-cohesion` — the only packs
that send images; Jev is text-only and cannot serve them).

Per-pack actions (probabilities → code, never prose):

| Pack | Action |
|---|---|
| `intake-router` | `safety_flag ≥ 0.8` → task refused with a clear error (no silent fallback). `needs_human ≥ 0.5` → `needs_review` flag on the brief. Approved-category vote adopted only when the LLM missed the taxonomy. Provider errors → no action (fail-open). |
| `copy-voice/claims/structure` | Merged into one composite `copy_quality` score (brand 0.35 / clarity 0.25 / CTA 0.2 / value 0.2). `≥ 0.80` pass, `0.60–0.80` human review, `< 0.60` rewrite. Blocking (`copy_qa_blocked`) only when `COPY_QA_ENFORCE=true`; copy is never dropped. Failing claim dimensions ride into the verifier prompt as extra scrutiny. |
| `planner-gate`, `verifier-pregate`, `sequence-cohesion` | Advisory audit trail (agreement calibration). They never flip a deterministic result today — the logs tell us which pack earns enforcement next. |

## 4. Question-writing rules (when adding a pack)

One judgment per question; positive framing (high = yes); Choice 2–255
options + `other` escape hatch; Score 2–10 ordered levels, lowest first;
Noul decisiveness = distance from 0.5. Never ask for counts, dates, hex
codes, or double negatives — judge in the model, compute in code.
Version questions + criteria + thresholds together (`version` field) and
replay the labeled set on any change.
