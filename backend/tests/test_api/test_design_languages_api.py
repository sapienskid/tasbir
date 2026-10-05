"""Design languages API tests — full-row exposure + provenance."""

H = {"x-api-key": "test-key"}

# "seed" = a built-in preset resolved live from styles.STYLE_PRESETS,
# "bundled" = a bundled brand system's own language (seeder-owned),
# "manual" = created or edited in the Studio.
SOURCES = {"seed", "bundled", "manual"}


async def test_list_exposes_full_row(authed_client):
    r = await authed_client.get("/api/design-languages", headers=H)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 5
    for row in rows:
        for field in ("id", "name", "base", "source", "is_active", "sort_order"):
            assert field in row, field
        assert row["source"] in SOURCES, row["source"]


async def test_list_omits_di_by_default_but_can_include_it(authed_client):
    """`di` is a large rules bundle — off for list views, on demand."""
    r = await authed_client.get("/api/design-languages", headers=H)
    assert all("di" not in row for row in r.json())

    r = await authed_client.get("/api/design-languages?include_di=true", headers=H)
    rows = r.json()
    assert all("di" in row for row in rows)
    swiss = next(row for row in rows if row["id"] == "swiss-editorial")
    assert swiss["di"], "built-in di bundle must not be empty"
    assert "layout_archetypes" in swiss["di"] or "style" in swiss["di"]


async def test_builtin_language_reports_seed_provenance(authed_client):
    r = await authed_client.get("/api/design-languages", headers=H)
    row = next(x for x in r.json() if x["id"] == "swiss-editorial")
    assert row["source"] == "seed"
    assert row["base"] == "swiss-editorial"
    assert row["is_active"] is True
    assert isinstance(row["sort_order"], int)


async def test_create_and_delete_custom_language(authed_client):
    r = await authed_client.post(
        "/api/design-languages",
        headers=H,
        json={"name": "Api Test Lang", "base": "bold-modern", "description": "tmp"},
    )
    assert r.status_code == 200, r.text
    row = r.json()
    language_id = row["id"]
    try:
        assert row["source"] == "manual"
        assert row["base"] == "bold-modern"
        # Created from a base preset: it inherits the base's rules.
        assert row["palette_tokens"]
    finally:
        r = await authed_client.delete(f"/api/design-languages/{language_id}", headers=H)
        assert r.status_code == 204, r.text


async def test_cannot_delete_builtin_language(authed_client):
    r = await authed_client.delete("/api/design-languages/swiss-editorial", headers=H)
    assert r.status_code == 422, r.text


async def test_styles_endpoint_reports_provenance(authed_client):
    """The DS style picker can tell built-ins from Studio-owned customs."""
    r = await authed_client.get("/api/design-systems/styles", headers=H)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 5
    for row in rows:
        assert row["source"] in SOURCES, row["source"]
        assert "is_active" in row
