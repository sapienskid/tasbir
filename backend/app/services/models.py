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
        "rpm": 30,
        "tpm": 16000,
        "rpd": 14400,
    },
    "gemma-4-26b-a4b-it": {
        "name": "Gemma 4 26B A4B",
        "category": "text",
        "vision": True,
        "rpm": 30,
        "tpm": 16000,
        "rpd": 14400,
    },
    "gemini-3.1-flash-lite": {
        "name": "Gemini 3.1 Flash Lite",
        "category": "text",
        "vision": True,
        "rpm": 15,
        "tpm": 250000,
        "rpd": 500,
    },
    "gemini-3.5-flash-lite": {
        "name": "Gemini 3.5 Flash Lite",
        "category": "text",
        "vision": True,
        "rpm": 15,
        "tpm": 250000,
        "rpd": 500,
    },
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash",
        "category": "text",
        "vision": True,
        "rpm": 7,
        "tpm": 9780,
        "rpd": 22,
    },
}

# Default fallback chains per primary model. Vision-capable models are the
# only valid fallbacks for the verifier path (image audit).
FALLBACK_CHAIN: dict[str, list[str]] = {
    "gemma-4-31b-it": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemma-4-26b-a4b-it"],
    "gemma-4-26b-a4b-it": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemma-4-31b-it"],
    "gemini-3.1-flash-lite": ["gemini-3.5-flash-lite", "gemma-4-31b-it"],
    "gemini-3.5-flash-lite": ["gemini-3.1-flash-lite", "gemma-4-31b-it"],
    "gemini-2.5-flash": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"],
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


def list_models() -> list[dict]:
    """Registry entries sorted by name, for the Studio dropdown."""
    return [
        {"id": mid, **meta}
        for mid, meta in sorted(MODEL_REGISTRY.items(), key=lambda kv: kv[1]["name"])
    ]


def model_info(model: str) -> dict | None:
    return MODEL_REGISTRY.get(model)


def default_fallbacks(model: str) -> list[str]:
    """Default fallback chain for a primary model (vision-capable only)."""
    return list(FALLBACK_CHAIN.get(model, FALLBACK_CHAIN.get("gemini-3.1-flash-lite", [])))
