"""Platforms API + DB-backed dimension tests."""

from app.services.formats import get_format_info
from app.services.platforms import family_of, get_platform_dims, list_platforms
from app.services.templates import format_family

H = {"x-api-key": "test-key"}


async def test_platforms_seeded_and_listed(authed_client):
    r = await authed_client.get("/api/platforms", headers=H)
    assert r.status_code == 200, r.text
    rows = r.json()
    ids = {row["id"] for row in rows}
    assert "instagram-square" in ids
    assert "instagram-carousel-portrait" in ids
    assert "linkedin-post" in ids
    square = next(row for row in rows if row["id"] == "instagram-square")
    assert square["width"] == 1080 and square["height"] == 1080
    linkedin = next(row for row in rows if row["id"] == "linkedin-post")
    assert linkedin["family"] == "landscape"


async def test_platforms_crud(authed_client):
    r = await authed_client.post(
        "/api/platforms",
        headers=H,
        json={
            "id": "mastodon-post",
            "name": "Mastodon",
            "width": 1200,
            "height": 630,
            "family": "landscape",
        },
    )
    assert r.status_code == 201, r.text

    r = await authed_client.put(
        "/api/platforms/mastodon-post",
        headers=H,
        json={"height": 675},
    )
    assert r.status_code == 200, r.text
    assert r.json()["height"] == 675

    r = await authed_client.get("/api/platforms/mastodon-post", headers=H)
    assert r.json()["width"] == 1200

    r = await authed_client.delete("/api/platforms/mastodon-post", headers=H)
    assert r.status_code == 204
    r = await authed_client.get("/api/platforms/mastodon-post", headers=H)
    assert r.status_code == 404


async def test_platforms_validate_family_and_id(authed_client):
    r = await authed_client.post(
        "/api/platforms",
        headers=H,
        json={"id": "bad", "width": 100, "height": 100, "family": "wide"},
    )
    assert r.status_code == 422
    r = await authed_client.post(
        "/api/platforms", headers=H, json={"id": "Bad/Id", "width": 100, "height": 100}
    )
    assert r.status_code == 422


async def test_new_platform_usable_by_pipeline(authed_client):
    await authed_client.post(
        "/api/platforms",
        headers=H,
        json={
            "id": "mastodon-post",
            "name": "Mastodon",
            "width": 1200,
            "height": 630,
            "family": "landscape",
        },
    )
    assert get_format_info("mastodon-post").width == 1200
    assert family_of("mastodon-post") == "landscape"
    assert format_family("mastodon-post") == "landscape"


def test_format_family_uses_db_family():
    assert format_family("linkedin-post") == "landscape"
    assert format_family("instagram-carousel-portrait") == "portrait"
    # Carousel slide ids resolve to their base platform's family.
    assert format_family("instagram-carousel-1") == "square"
    assert format_family("instagram-carousel-portrait-2") == "portrait"


def test_platform_dims_resolve():
    assert get_platform_dims("instagram-carousel") == (1080, 1080)
    assert get_platform_dims("instagram-carousel-portrait") == (1080, 1350)
    assert get_platform_dims("linkedin-post") == (1200, 627)
    assert list_platforms()
