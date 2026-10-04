"""Free-tier model registry API + multi-model routing tests."""

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


async def test_call_llm_walks_fallback_chain(monkeypatch):
    """Route first, then each model in the agent chain — all via Gateway."""
    from types import SimpleNamespace

    from app.services import llm as llm_mod

    tried: list[str] = []

    async def fake_post(payload):
        tried.append(payload["model"])
        if len(tried) < 3:
            raise RuntimeError("target down")
        return ({"choices": [{"message": {"role": "assistant",
                                          "content": "ok"}}]}, "gemini-3.1-flash-lite")

    monkeypatch.setattr(llm_mod, "_compat_post", fake_post)

    async def _cfg(name):
        return SimpleNamespace(model="gemma-4-26b-a4b-it",
                               fallback_models=["gemini-3.1-flash-lite"])

    monkeypatch.setattr("app.services.agents.get_agent_config", _cfg)

    out = await llm_mod.call_llm("strategist", "sys", "user")
    assert out == "ok"
    assert tried[0] == "dynamic/tasbir-fast"  # route leads
    assert tried[1] == "google-ai-studio/gemma-4-26b-a4b-it"
    assert tried[2] == "google-ai-studio/gemini-3.1-flash-lite"


async def test_call_llm_raises_when_gateway_down(monkeypatch):
    """No silent direct fallback: total Gateway failure raises."""
    from types import SimpleNamespace

    from app.services import llm as llm_mod

    async def always_down(payload):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(llm_mod, "_compat_post", always_down)

    async def _cfg(name):
        return SimpleNamespace(model="gemma-4-26b-a4b-it", fallback_models=[])

    monkeypatch.setattr("app.services.agents.get_agent_config", _cfg)

    try:
        await llm_mod.call_llm("strategist", "sys", "user")
    except RuntimeError as e:
        assert "gateway down" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
