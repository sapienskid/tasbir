"""Free-tier model registry API + multi-model routing tests."""

from unittest.mock import patch

H = {"x-api-key": "test-key"}


async def test_models_endpoint_lists_registry(authed_client):
    r = await authed_client.get("/api/models", headers=H)
    assert r.status_code == 200, r.text
    ids = {m["id"] for m in r.json()["models"]}
    assert "gemma-4-31b-it" in ids
    assert "gemma-4-26b-a4b-it" in ids
    assert "gemini-3.1-flash-lite" in ids
    assert "gemini-3.5-flash-lite" in ids


def test_model_routes_assign_role_models():
    from app.services.models import MODEL_ROUTES

    assert MODEL_ROUTES["copywriter"] == "gemma-4-31b-it"
    assert MODEL_ROUTES["designer"] == "gemma-4-31b-it"
    assert MODEL_ROUTES["strategist"] == "gemma-4-26b-a4b-it"
    assert MODEL_ROUTES["verifier"] == "gemini-3.1-flash-lite"
    # gemini-3.5-flash-lite stays in active use somewhere.
    assert MODEL_ROUTES["brand_campaigns"] == "gemini-3.5-flash-lite"


async def test_call_llm_walks_fallback_chain():
    from app.services import llm as llm_mod

    tried: list[str] = []

    async def fake_retry(llm, messages, max_retries=3, agent_role=""):
        tried.append(llm.model)
        raise RuntimeError("model down")

    with patch("app.services.llm.call_llm_with_retry", fake_retry):
        with patch("app.services.llm.get_settings") as gs:
            gs.return_value.openrouter_api_key = ""
            gs.return_value.gemini_api_key = "k"
            try:
                await llm_mod.call_llm("strategist", "sys", "user")
            except RuntimeError:
                pass

    assert len(tried) >= 2  # primary + at least one fallback
    assert tried[0] == "gemma-4-26b-a4b-it"
    assert "gemini-3.1-flash-lite" in tried
