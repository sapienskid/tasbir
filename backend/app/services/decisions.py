"""Decision models — Jev + Clef behind one System One interface, via Cloudflare.

Both models share the ``{state, questions} → {answers}`` shape (Jev-native,
Clef-compatible). All calls go through Cloudflare so no TypeSafe key is ever
needed: Jev runs as third-party ``typesafe/jev`` (Unified Billing), Clef as
``@cf/cloudflare/clef[-flash]`` (Neurons). REST ``ai/run`` envelopes differ
(Jev ``{result}`` vs Clef ``{success, result}``) — unwrapped here.

Question rules (docs.typesafe.ai): one judgment per question, positive
framing (high=yes), Choice 2–255 options + ``other`` escape hatch, Score 2–10
ordered levels lowest-first, Noul decisiveness = distance from 0.5. Never ask
for counts, dates, hex codes, or double negatives — judge in the model,
compute in code.
"""

from __future__ import annotations

import logging
import time

from app.config import get_settings

log = logging.getLogger(__name__)

TEXT_TIMEOUT = 30.0
VISION_TIMEOUT = 90.0

# Provider → REST model id. clef-flash does fast text work, clef-full is
# vision/precision. jev stays wired (third-party REST shape) as an opt-in
# third provider — off by default until Gateway credits exist.
PROVIDERS: dict[str, str] = {
    "jev": "typesafe/jev",
    "clef-flash": "@cf/cloudflare/clef-flash",
    "clef": "@cf/cloudflare/clef",
}

_API_BASE = "https://api.cloudflare.com/client/v4/accounts"


def providers_configured() -> bool:
    settings = get_settings()
    return bool(settings.resolved_cf_account_id and settings.resolved_cf_token)


def provider_order() -> list[str]:
    settings = get_settings()
    order = [p.strip() for p in (settings.decision_provider_order or "").split(",") if p.strip()]
    known = [p for p in order if p in PROVIDERS]
    return known or ["clef-flash", "clef"]


def noul_confidence(p: float) -> float:
    """Confidence-style decisiveness for a Noul probability."""
    return abs(2.0 * float(p) - 1.0)


def choice_confidence(probs: dict[str, float]) -> float:
    """Official Choice confidence from the probability distribution."""
    n = len(probs)
    if n < 2:
        return 0.0
    pmax = max(float(v) for v in probs.values())
    return max(0.0, min(1.0, (pmax - 1.0 / n) / (1.0 - 1.0 / n)))


async def _call_provider(
    provider: str,
    state: dict | str,
    questions: dict,
    images: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """POST one System One request to a single provider via Cloudflare REST."""
    import httpx

    settings = get_settings()
    if not providers_configured():
        raise RuntimeError("Cloudflare decision providers not configured")
    model_id = PROVIDERS[provider]
    base = f"{_API_BASE}/{settings.resolved_cf_account_id}"
    headers = {
        "Authorization": f"Bearer {settings.resolved_cf_token}",
        "Content-Type": "application/json",
    }
    if settings.cf_gateway_id:
        headers["cf-aig-gateway-id"] = settings.cf_gateway_id
    if provider == "jev":
        # Third-party REST shape (docs: ai/models/typesafe/jev): the model
        # goes in the body and state/questions nest under "input".
        url = f"{base}/ai/run"
        body: dict = {"model": model_id, "input": {"state": state, "questions": questions}}
        if images:
            raise ValueError("Jev is text-only; route image packs to Clef")
    else:
        url = f"{base}/ai/run/{model_id}"
        body = {"state": state, "questions": questions}
        body["model"] = "clef-flash" if provider == "clef-flash" else "clef"
        if images:
            body["images"] = images
    timeout = VISION_TIMEOUT if images else TEXT_TIMEOUT
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=body)
        try:
            resp.raise_for_status()
        except Exception:
            # Surface the API error body (no secrets in it) for diagnosis.
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    # Jev REST: {result: {...}} or the answer object directly;
    # Clef REST: {success, result: {...}}.
    result = data.get("result", data) if isinstance(data, dict) else {}
    if not isinstance(result, dict) or "answers" not in result:
        result = data if isinstance(data, dict) and "answers" in data else result
    answers = result.get("answers", {}) if isinstance(result, dict) else {}
    elapsed = time.monotonic() - started
    log.info(
        "[decide] provider=%s questions=%d latency=%.2fs model=%s",
        provider, len(questions), elapsed, result.get("model", provider),
    )
    return {
        "provider": provider,
        "model": str(result.get("model", provider)),
        "answers": answers,
        "usage": result.get("usage", {}),
        "latency_s": round(elapsed, 3),
        "metadata": metadata or {},
    }


def _disagree(a: dict, b: dict) -> bool:
    """True when two answer maps disagree enough to escalate."""
    for qid, ans_a in a.items():
        ans_b = b.get(qid)
        if not isinstance(ans_b, dict):
            continue
        if ans_a.get("type") == "choice" and ans_b.get("type") == "choice":
            if ans_a.get("choice") != ans_b.get("choice"):
                return True
        for key in ("noul", "score"):
            if key in ans_a and key in ans_b:
                try:
                    if abs(float(ans_a[key]) - float(ans_b[key])) > 0.25:
                        return True
                except (TypeError, ValueError):
                    continue
    return False


async def decide(
    pack_id: str,
    state: dict | str,
    questions: dict | None = None,
    images: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Run a decision pack: primary provider first, fallback on failure.

    ``questions`` defaults to the pack definition in ``decision_packs``.
    Fail-open: raises only when every provider fails (callers catch and
    continue the pipeline). Calibration dual-runs a second provider on a
    sample and logs agreement.
    """
    from app.services.decision_packs import get_pack

    pack = get_pack(pack_id)
    questions = questions or pack["questions"]
    order = list(pack.get("providers") or provider_order())
    if images and "jev" in order:
        order = [p for p in order if p != "jev"] or ["clef"]
    meta = {"pack_id": pack_id, **(metadata or {})}
    last_error: Exception | None = None
    primary_result: dict | None = None
    for provider in order:
        try:
            result = await _call_provider(provider, state, questions, images, meta)
            result["pack_id"] = pack_id
            result["pack_version"] = pack.get("version", 1)
            if primary_result is None:
                primary_result = result
                break
            return result
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning("[decide] %s/%s failed (%s) — trying next", pack_id, provider, e)
    if primary_result is None:
        raise last_error or RuntimeError(f"All decision providers failed for {pack_id}")

    # Calibration: dual-run a second provider on a sample, log agreement.
    try:
        settings = get_settings()
        rate = float(settings.decision_calibration_rate or 0.0)
        others = [p for p in order if p != primary_result["provider"]]
        import random

        if rate > 0 and others and random.random() < rate:
            try:
                second = await _call_provider(
                    others[0], state, questions, images, meta
                )
                disagree = _disagree(primary_result["answers"], second.get("answers", {}))
                log.info(
                    "[decide] calibration %s primary=%s second=%s disagree=%s",
                    pack_id, primary_result["provider"], second.get("provider"), disagree,
                )
                primary_result["calibration"] = {
                    "second_provider": second.get("provider"),
                    "disagree": disagree,
                }
            except Exception as e:  # noqa: BLE001
                log.warning("[decide] calibration second call failed: %s", e)
    except Exception:  # noqa: BLE001
        pass
    return primary_result
