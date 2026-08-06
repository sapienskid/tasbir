"""Agents API tests — DB-backed agent config CRUD + graph topology."""

from app.services.agents import invalidate_agent_config


async def test_list_agents_seeded(authed_client):
    r = await authed_client.get("/api/agents", headers={"x-api-key": "test-key"})
    assert r.status_code == 200, r.text
    agents = r.json()
    names = {a["name"] for a in agents}
    assert "strategist" in names
    assert "copywriter" in names
    assert "designer" in names
    assert "verifier" in names
    # all 10 roles seeded
    assert len(agents) >= 10


async def test_get_agent(authed_client):
    r = await authed_client.get("/api/agents/strategist", headers={"x-api-key": "test-key"})
    assert r.status_code == 200, r.text
    agent = r.json()
    assert agent["name"] == "strategist"
    assert agent["persona"] == "Aura Vance"
    assert "Aura Vance" in agent["system_prompt"]
    assert agent["model"]  # from MODEL_ROUTES seed
    assert agent["temperature"] > 0
    assert agent["max_tokens"] > 0


async def test_get_agent_unknown_404(authed_client):
    r = await authed_client.get("/api/agents/nope", headers={"x-api-key": "test-key"})
    assert r.status_code == 404


async def test_update_agent(authed_client):
    r = await authed_client.put(
        "/api/agents/strategist",
        headers={"x-api-key": "test-key"},
        json={"persona": "Aura Vance II", "model": "gemini-3.5-flash-lite"},
    )
    assert r.status_code == 200, r.text
    agent = r.json()
    assert agent["persona"] == "Aura Vance II"
    assert agent["model"] == "gemini-3.5-flash-lite"

    # persisted + cache invalidated — a fresh GET reflects the edit
    r2 = await authed_client.get("/api/agents/strategist", headers={"x-api-key": "test-key"})
    assert r2.json()["persona"] == "Aura Vance II"

    # and the DB-backed loader returns it too
    from app.services.agents import get_agent_config

    cfg = await get_agent_config("strategist")
    assert cfg.persona == "Aura Vance II"
    assert cfg.model == "gemini-3.5-flash-lite"
    invalidate_agent_config()


async def test_update_agent_empty_prompt_422(authed_client):
    r = await authed_client.put(
        "/api/agents/strategist",
        headers={"x-api-key": "test-key"},
        json={"system_prompt": "   "},
    )
    assert r.status_code == 422


async def test_update_agent_bad_model_422(authed_client):
    r = await authed_client.put(
        "/api/agents/strategist",
        headers={"x-api-key": "test-key"},
        json={"model": "gemini 3.5 flash"},
    )
    assert r.status_code == 422

    r2 = await authed_client.put(
        "/api/agents/strategist",
        headers={"x-api-key": "test-key"},
        json={"fallback_models": ["openai/gpt-4o", "bad model!"]},
    )
    assert r2.status_code == 422

    r3 = await authed_client.put(
        "/api/agents/strategist",
        headers={"x-api-key": "test-key"},
        json={"model": "gemini-3.5-flash-lite"},
    )
    assert r3.status_code == 200


async def test_reset_agent_restores_seed(authed_client):
    await authed_client.put(
        "/api/agents/strategist",
        headers={"x-api-key": "test-key"},
        json={"persona": "Clobbered", "system_prompt": "clobbered"},
    )
    r = await authed_client.post(
        "/api/agents/strategist/reset", headers={"x-api-key": "test-key"}
    )
    assert r.status_code == 200, r.text
    agent = r.json()
    assert agent["persona"] == "Aura Vance"
    assert "Aura Vance" in agent["system_prompt"]


async def test_agent_graph_topology(authed_client):
    r = await authed_client.get("/api/agents/graph", headers={"x-api-key": "test-key"})
    assert r.status_code == 200, r.text
    spec = r.json()
    ids = {n["id"] for n in spec["nodes"]}
    assert {"start", "strategist", "planner", "copywriter", "end"} <= ids
    # the per-format chain is inlined on the same canvas
    assert {"template", "designer", "renderer", "verifier"} <= ids
    assert "subflow" not in spec
    # enrichment: agent nodes carry live persona/model
    strategist = next(n for n in spec["nodes"] if n["id"] == "strategist")
    assert strategist["persona"] == "Aura Vance"
    # aux lanes cover the non-pipeline agents
    lane_agents = {a["name"] for lane in spec["aux_lanes"] for a in lane["agents"]}
    assert {"brand_vision", "brand_tokens", "brand_campaigns"} <= lane_agents
    assert {"template_vision", "template_author"} <= lane_agents
    assert "editor_chat" in lane_agents


async def test_resolve_model_falls_back_to_defaults():
    from app.services.agents import resolve_model

    invalidate_agent_config()
    assert resolve_model("strategist")  # non-empty
    assert resolve_model("definitely_not_a_role")  # non-empty default


async def test_prompt_preview_assembles_system_and_user(authed_client):
    r = await authed_client.post(
        "/api/agents/designer/prompt-preview",
        headers={"x-api-key": "test-key"},
        json={},
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert "system_prompt" in p
    assert "user_prompt" in p
    # designer placeholders are resolved from the design system at preview time
    assert "{TEMPLATE_CONTEXT}" not in p["system_prompt"]
    assert "var(--font-display)" in p["system_prompt"]
    assert "PLATFORM: instagram-square" in p["user_prompt"]


async def test_prompt_preview_strategist_shows_categories(authed_client):
    r = await authed_client.post(
        "/api/agents/strategist/prompt-preview",
        headers={"x-api-key": "test-key"},
        json={},
    )
    assert r.status_code == 200, r.text
    user_prompt = r.json()["user_prompt"]
    assert "APPROVED CATEGORY LABELS" in user_prompt
    assert "WRITING" in user_prompt
