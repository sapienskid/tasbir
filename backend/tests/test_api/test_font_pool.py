"""Curated font pool API + brand-agent pool tests."""

H = {"x-api-key": "test-key"}


async def test_font_pool_seeded_and_listed(authed_client):
    r = await authed_client.get("/api/fonts/pool", headers=H)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(f["family"] == "Space Grotesk" for f in rows)
    assert any(f["role"] == "display" for f in rows)


async def test_font_pool_crud(authed_client):
    r = await authed_client.post(
        "/api/fonts/pool",
        headers=H,
        json={"family": "Test Mono", "role": "mono", "weights": [400, 700], "style": "monospace"},
    )
    assert r.status_code == 201, r.text

    r = await authed_client.put(
        "/api/fonts/pool/Test Mono", headers=H, json={"weights": [400]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["weights"] == [400]

    r = await authed_client.delete("/api/fonts/pool/Test Mono", headers=H)
    assert r.status_code == 204
    r = await authed_client.get("/api/fonts/pool/Test Mono", headers=H)
    assert r.status_code == 404


async def test_font_pool_feeds_brand_agent_prompt(authed_client):
    from app.services.fonts import font_pool_for_prompt

    text = await font_pool_for_prompt()
    assert "Space Grotesk" in text
    assert "display" in text
