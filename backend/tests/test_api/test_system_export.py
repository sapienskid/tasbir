"""System export/import API tests."""

from app.services import system_export

H = {"x-api-key": "test-key"}


async def test_export_snapshots_all_config_tables(authed_client):
    r = await authed_client.get("/api/system/export", headers=H)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["schema_version"] == system_export.SCHEMA_VERSION
    for table in system_export.TABLES:
        assert table in doc, table
        assert isinstance(doc[table], list)
    # The seeded default system + its templates are present.
    assert len(doc["design_systems"]) >= 1
    assert len(doc["templates"]) >= 1
    assert len(doc["platforms"]) >= 1
    assert len(doc["fonts"]) >= 1
    assert len(doc["agents"]) >= 1
    assert len(doc["app_settings"]) >= 1
    # The five built-in design languages are part of the backup, and each row
    # carries its full rules bundle (di) so a restore is lossless.
    langs = doc["design_languages"]
    assert len(langs) >= 5
    by_id = {row["id"]: row for row in langs}
    assert "swiss-editorial" in by_id
    assert by_id["swiss-editorial"]["source"] == "seed"
    assert isinstance(by_id["swiss-editorial"]["di"], dict)
    assert by_id["swiss-editorial"]["di"], "built-in di bundle must not be empty"
    # No runtime tables leak into the snapshot.
    assert "generation_tasks" not in doc
    assert "audit_logs" not in doc


async def test_export_is_json_serializable(authed_client):
    import json

    r = await authed_client.get("/api/system/export", headers=H)
    assert r.status_code == 200, r.text
    # Datetimes are serialized to ISO strings; the whole doc round-trips.
    json.dumps(r.json())


async def test_import_upserts_and_round_trips(authed_client):
    # Grab a fresh snapshot, then mutate an existing row + add a new one.
    r = await authed_client.get("/api/system/export", headers=H)
    assert r.status_code == 200, r.text
    doc = r.json()

    assert len(doc["platforms"]) >= 1
    first = doc["platforms"][0]
    first_id = first["id"]
    first["name"] = "Renamed by import"

    new_platform = {
        "id": "mastodon-post",
        "name": "Mastodon",
        "width": 1200,
        "height": 675,
        "family": "landscape",
        "is_active": True,
        "sort_order": 99,
    }
    doc["platforms"].append(new_platform)

    r = await authed_client.post("/api/system/import", headers=H, json={"payload": doc})
    assert r.status_code == 200, r.text
    applied = r.json()["applied"]
    assert applied["platforms"] == len(doc["platforms"])

    # Verify the upsert landed.
    r = await authed_client.get("/api/platforms", headers=H)
    assert r.status_code == 200, r.text
    platforms = r.json()
    by_id = {p["id"]: p for p in platforms}
    assert by_id[first_id]["name"] == "Renamed by import"
    assert by_id["mastodon-post"]["name"] == "Mastodon"


async def test_import_keeps_rows_missing_from_payload(authed_client):
    r = await authed_client.get("/api/system/export", headers=H)
    doc = r.json()
    # Drop every platform except the first — merge must NOT delete the rest.
    doc["platforms"] = doc["platforms"][:1]
    kept = doc["platforms"][0]["id"]

    r = await authed_client.post("/api/system/import", headers=H, json={"payload": doc})
    assert r.status_code == 200, r.text

    r = await authed_client.get("/api/platforms", headers=H)
    ids = {p["id"] for p in r.json()}
    assert kept in ids
    assert len(ids) >= 1
    # The seeded library (9 platforms) is untouched beyond the upserted row.
    assert len(ids) >= 9


async def test_import_rejects_bad_schema_version(authed_client):
    r = await authed_client.post(
        "/api/system/import",
        headers=H,
        json={"payload": {"schema_version": 999, "design_systems": []}},
    )
    assert r.status_code == 422, r.text
    assert "schema_version" in r.json()["detail"]


async def test_import_rejects_missing_tables(authed_client):
    r = await authed_client.post(
        "/api/system/import",
        headers=H,
        json={"payload": {"schema_version": 2, "design_systems": []}},
    )
    assert r.status_code == 422, r.text
    assert "missing table" in r.json()["detail"]


async def test_import_accepts_v1_payload_without_design_languages(authed_client):
    """A pre-language backup still imports; its missing table is not an error."""
    r = await authed_client.get("/api/system/export", headers=H)
    doc = r.json()
    # Downgrade to a v1 document: drop the table introduced in v2.
    doc["schema_version"] = 1
    doc.pop("design_languages", None)

    r = await authed_client.post("/api/system/import", headers=H, json={"payload": doc})
    assert r.status_code == 200, r.text
    assert r.json()["applied"]["design_languages"] == 0
    # Nothing was deleted — the local built-in languages are still there.
    r = await authed_client.get("/api/design-languages", headers=H)
    assert r.status_code == 200, r.text
    assert len(r.json()) >= 5


async def test_import_restores_custom_design_language(authed_client):
    """A custom (Studio-owned) language survives an export/import round-trip."""
    r = await authed_client.post(
        "/api/design-languages",
        headers=H,
        json={"name": "Round Trip", "base": "swiss-editorial", "description": "restore me"},
    )
    assert r.status_code == 200, r.text
    language_id = r.json()["id"]
    try:
        r = await authed_client.get("/api/system/export", headers=H)
        doc = r.json()
        langs = {row["id"]: row for row in doc["design_languages"]}
        assert language_id in langs
        assert langs[language_id]["source"] == "manual"
        assert langs[language_id]["description"] == "restore me"

        # Remove it, then restore from the snapshot.
        r = await authed_client.delete(f"/api/design-languages/{language_id}", headers=H)
        assert r.status_code == 204, r.text
        r = await authed_client.get("/api/design-languages", headers=H)
        assert language_id not in {row["id"] for row in r.json()}

        r = await authed_client.post("/api/system/import", headers=H, json={"payload": doc})
        assert r.status_code == 200, r.text
        r = await authed_client.get("/api/design-languages", headers=H)
        restored = {row["id"]: row for row in r.json()}
        assert language_id in restored
        assert restored[language_id]["description"] == "restore me"
    finally:
        # The DB is session-scoped — don't leak this language into later tests.
        await authed_client.delete(f"/api/design-languages/{language_id}", headers=H)


async def test_import_does_not_clobber_built_in_languages(authed_client):
    """Code-owned seed rows resolve live from STYLE_PRESETS, never from a payload."""
    from app.services.styles import STYLE_PRESETS

    r = await authed_client.get("/api/system/export", headers=H)
    doc = r.json()
    rows = doc["design_languages"]
    seed_ids = {row["id"] for row in rows if row.get("source") == "seed"}
    custom_ids = {row["id"] for row in rows} - seed_ids
    assert "swiss-editorial" in seed_ids
    target = next(row for row in rows if row["id"] == "swiss-editorial")
    # Corrupt the fields that only bookkeeping would care about.
    target["name"] = "HIJACKED"
    target["is_active"] = False
    target["sort_order"] = 4242

    r = await authed_client.post("/api/system/import", headers=H, json={"payload": doc})
    assert r.status_code == 200, r.text
    # Only the custom (Studio-owned) rows are applied; every seed row is skipped.
    assert r.json()["applied"]["design_languages"] == len(custom_ids)

    r = await authed_client.get("/api/design-languages", headers=H)
    row = next(x for x in r.json() if x["id"] == "swiss-editorial")
    assert row["name"] == STYLE_PRESETS["swiss-editorial"]["label"]
    assert row["is_active"] is True


async def test_import_rejects_unknown_keys(authed_client):
    r = await authed_client.get("/api/system/export", headers=H)
    doc = r.json()
    doc["garbage"] = True
    r = await authed_client.post("/api/system/import", headers=H, json={"payload": doc})
    assert r.status_code == 422, r.text
    assert "unknown top-level keys" in r.json()["detail"]


async def test_export_requires_auth(authed_client):
    r = await authed_client.get("/api/system/export")
    assert r.status_code == 401, r.text


async def test_import_requires_auth(authed_client):
    r = await authed_client.post("/api/system/import", json={"payload": {}})
    assert r.status_code == 401, r.text
