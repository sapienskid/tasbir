"""Free-tier model registry — the models the pipeline can use, their rate
limits, and the default fallback chains.

Rates come from the Gemini free-tier quota table:
  Gemma 4 26B/31B     30 RPM · 16K TPM · 14.4K RPD (text, multimodal)
  Gemini 3.1 Flash Lite 15 RPM · 250K TPM · 500 RPD (text-out)
  Gemini 3.5 Flash Lite 15 RPM · 250K TPM · 500 RPD (text-out)
  Antigravity (managed agent) — different API paradigm, not a drop-in LLM;
  intentionally omitted from routing.

The Studio exposes these via GET /api/models so the model + fallback-model
fields are dropdowns, not free text.
"""

from __future__ import annotations

MODEL_REGISTRY: dict[str, dict] = {
    "gemma-4-31b-it": {
        "name": "Gemma 4 31B",
        "category": "text",
        "vision": True,
        # Google AI Studio free tier, per model.
        "rpm": 30,
        "tpm": 16000,
        "rpd": 14400,
        # Verified live: echoes the prompt instead of emitting a bare JSON
        # object, so JSON-only agents must not be routed here.
        "json_ok": False,
    },
    "gemma-4-26b-a4b-it": {
        "name": "Gemma 4 26B A4B",
        "category": "text",
        "vision": True,
        "rpm": 30,
        "tpm": 16000,
        "rpd": 14400,
        "json_ok": False,
    },
    "gemini-3.1-flash-lite": {
        "name": "Gemini 3.1 Flash Lite",
        "category": "text",
        "vision": True,
        "rpm": 15,
        "tpm": 250000,
        "rpd": 500,
        "json_ok": True,
    },
    "gemini-3.5-flash-lite": {
        "name": "Gemini 3.5 Flash Lite",
        "category": "text",
        "vision": True,
        "rpm": 15,
        "tpm": 250000,
        "rpd": 500,
        "json_ok": True,
    },
}

# Models that honor a strict "reply with only this JSON object" contract
# (verified live through the Gateway). JSON-only agents pin to this so a
# Gemma node in a route can never hand us prose we cannot parse.
JSON_MODEL = "gemini-3.1-flash-lite"
JSON_CAPABLE_MODELS: list[str] = [
    m for m, meta in MODEL_REGISTRY.items() if meta.get("json_ok")
]

# Retired model ids → replacement. gemini-2.5-flash is fully out (no
# credits): any stored agent row / fallback list still naming it resolves to
# gemini-3.1-flash-lite instead of failing at call time.
RETIRED_MODELS: dict[str, str] = {
    "gemini-2.5-flash": "gemini-3.1-flash-lite",
}


def resolve_model_id(model: str) -> str:
    """Map a configured model id to a usable one (retired → replacement)."""
    return RETIRED_MODELS.get(model, model)

# Default fallback chains per primary model. Vision-capable models are the
# only valid fallbacks for the verifier path (image audit).
FALLBACK_CHAIN: dict[str, list[str]] = {
    "gemma-4-31b-it": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemma-4-26b-a4b-it"],
    "gemma-4-26b-a4b-it": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemma-4-31b-it"],
    "gemini-3.1-flash-lite": ["gemini-3.5-flash-lite", "gemma-4-31b-it"],
    "gemini-3.5-flash-lite": ["gemini-3.1-flash-lite", "gemma-4-31b-it"],
}

# Primary model per agent role. gemini-3.5-flash-lite stays in active use
# (brand_campaigns is low-volume); vision agents stay on battle-tested Gemini.
MODEL_ROUTES: dict[str, str] = {
    "strategist": "gemma-4-26b-a4b-it",
    "planner": "gemma-4-26b-a4b-it",
    "copywriter": "gemma-4-31b-it",
    "designer": "gemma-4-31b-it",
    "template_author": "gemma-4-26b-a4b-it",
    "verifier": "gemini-3.1-flash-lite",
    "template_vision": "gemini-3.1-flash-lite",
    "brand_vision": "gemini-3.1-flash-lite",
    "brand_tokens": "gemma-4-26b-a4b-it",
    "brand_campaigns": "gemini-3.5-flash-lite",
    "editor_chat": "gemini-3.1-flash-lite",
}

# Cloudflare dynamic-route tiers (Phase 1). The primary → fallback chains
# live in the Gateway UI as `dynamic/tasbir-{tier}` (versioned, no deploy);
# this map only decides which route an agent role calls. Keep the local
# FALLBACK_CHAIN above as the emergency fallback when the Gateway is down.
GATEWAY_TIERS: dict[str, list[str]] = {
    "fast": ["strategist", "planner", "brand_tokens", "brand_campaigns"],
    "creative": ["copywriter", "designer", "template_author", "editor_chat"],
    "vision": ["verifier", "template_vision", "brand_vision"],
}


def list_models() -> list[dict]:
    """Registry entries sorted by name, for the Studio dropdown."""
    return [
        {"id": mid, **meta}
        for mid, meta in sorted(MODEL_REGISTRY.items(), key=lambda kv: kv[1]["name"])
    ]


def model_info(model: str) -> dict | None:
    return MODEL_REGISTRY.get(model)


def default_fallbacks(model: str) -> list[str]:
    """Default fallback chain for a primary model (vision-capable only).

    Retired ids resolve first, so a stored ``gemini-2.5-flash`` row still
    gets a working chain instead of a dead one.
    """
    model = resolve_model_id(model)
    return list(FALLBACK_CHAIN.get(model, FALLBACK_CHAIN.get("gemini-3.1-flash-lite", [])))
