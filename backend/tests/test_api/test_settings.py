"""Runtime settings API tests."""

H = {"x-api-key": "test-key"}


async def test_settings_seeded_with_defaults(authed_client):
    r = await authed_client.get("/api/settings", headers=H)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["values"]["verifier.max_retries"] == 3
    assert data["values"]["copywriter.concurrency"] == 2
    assert data["values"]["vision.min_interval_seconds"] == 5.0
    assert data["values"]["chat.html_cap_chars"] == 80000
    assert data["values"]["templates.recent_limit"] == 8


async def test_settings_update_and_reset(authed_client):
    r = await authed_client.put(
        "/api/settings",
        headers=H,
        json={"values": {"verifier.max_retries": 5, "copywriter.concurrency": 3}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["values"]["verifier.max_retries"] == 5
    assert r.json()["values"]["copywriter.concurrency"] == 3

    # Runtime readers honor the knob.
    from app.services.settings import get_runtime_setting

    assert await get_runtime_setting("verifier.max_retries") == 5
    assert await get_runtime_setting("copywriter.concurrency") == 3

    r = await authed_client.post("/api/settings/reset", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["values"]["verifier.max_retries"] == 3


async def test_settings_ignores_unknown_keys(authed_client):
    r = await authed_client.put(
        "/api/settings", headers=H, json={"values": {"not.a.knob": 99}}
    )
    assert r.status_code == 200, r.text
    assert "not.a.knob" not in r.json()["values"]


async def test_settings_expose_type_contract(authed_client):
    """The Studio renders controls from `type`/`min`/`max` — no hardcoded keys."""
    r = await authed_client.get("/api/settings", headers=H)
    assert r.status_code == 200, r.text
    defaults = r.json()["defaults"]
    assert defaults["publish.enabled"]["type"] == "bool"
    assert defaults["verifier.max_retries"]["type"] == "int"
    assert defaults["verifier.max_retries"]["min"] == 0
    assert defaults["vision.min_interval_seconds"]["type"] == "float"
    # Every knob declares a type the UI knows how to render.
    for key, spec in defaults.items():
        assert spec["type"] in ("int", "float", "bool"), key
        assert spec["description"]


async def test_settings_reject_non_boolean_for_bool_knob(authed_client):
    """A bool knob must not accept 1/"true" (the old Number() coercion bug)."""
    for bad in (1, 0, "true", "false", 1.0):
        r = await authed_client.put(
            "/api/settings", headers=H, json={"values": {"publish.enabled": bad}}
        )
        assert r.status_code == 422, (bad, r.text)
        assert "publish.enabled" in r.json()["detail"]


async def test_settings_accept_real_boolean(authed_client):
    r = await authed_client.put(
        "/api/settings", headers=H, json={"values": {"publish.enabled": False}}
    )
    assert r.status_code == 200, r.text
    assert r.json()["values"]["publish.enabled"] is False

    r = await authed_client.post("/api/settings/reset", headers=H)
    assert r.json()["values"]["publish.enabled"] is True


async def test_settings_reject_out_of_range_and_wrong_type(authed_client):
    cases = [
        ({"verifier.max_retries": -1}, "verifier.max_retries"),
        ({"verifier.max_retries": 999}, "verifier.max_retries"),
        ({"verifier.max_retries": "abc"}, "verifier.max_retries"),
        ({"verifier.max_retries": 2.5}, "verifier.max_retries"),
        ({"verifier.max_retries": True}, "verifier.max_retries"),
        ({"copywriter.concurrency": 0}, "copywriter.concurrency"),
        ({"vision.min_interval_seconds": "5"}, "vision.min_interval_seconds"),
    ]
    for values, key in cases:
        r = await authed_client.put("/api/settings", headers=H, json={"values": values})
        assert r.status_code == 422, (values, r.text)
        assert key in r.json()["detail"]


async def test_settings_rejection_is_atomic(authed_client):
    """One bad value rejects the whole batch — nothing is written."""
    before = (await authed_client.get("/api/settings", headers=H)).json()["values"]
    r = await authed_client.put(
        "/api/settings",
        headers=H,
        json={
            "values": {
                "verifier.max_retries": 7,  # valid
                "publish.enabled": 1,  # invalid
            }
        },
    )
    assert r.status_code == 422, r.text
    after = (await authed_client.get("/api/settings", headers=H)).json()["values"]
    assert after == before, "a rejected PUT must not persist the valid key either"


async def test_settings_accepts_float_for_float_knob(authed_client):
    r = await authed_client.put(
        "/api/settings", headers=H, json={"values": {"vision.min_interval_seconds": 1.5}}
    )
    assert r.status_code == 200, r.text
    assert r.json()["values"]["vision.min_interval_seconds"] == 1.5
    await authed_client.post("/api/settings/reset", headers=H)


async def test_settings_meta_publishes_vocabularies(authed_client):
    from app.services.fonts import VALID_ROLES
    from app.services.platforms import VALID_FAMILIES

    r = await authed_client.get("/api/settings/meta", headers=H)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["families"] == sorted(VALID_FAMILIES)
    assert set(data["font_roles"]) == set(VALID_ROLES)
