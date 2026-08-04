"""System export/import API tests."""

from app.services import system_export

H = {"x-api-key": "test-key"}


async def test_export_snapshots_all_config_tables(authed_client):
    r = await authed_client.get("/api/system/export", headers=H)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["schema_version"] == 1
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
        json={"payload": {"schema_version": 1, "design_systems": []}},
    )
    assert r.status_code == 422, r.text
    assert "missing table" in r.json()["detail"]


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
