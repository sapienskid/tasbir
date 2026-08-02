"""Google Fonts search endpoint tests — service fetch is mocked."""

from unittest.mock import patch


async def test_fonts_search_returns_matches(authed_client):
    fake = [
        {
            "family": "Inter",
            "category": "sans-serif",
            "variants": ["regular", "500", "700"],
        },
        {
            "family": "Newsreader",
            "category": "serif",
            "variants": ["regular", "italic"],
        },
    ]
    with patch("app.api.fonts.search_fonts", return_value=fake) as m:
        r = await authed_client.get(
            "/api/fonts/search?q=inter", headers={"x-api-key": "test-key"}
        )
    assert r.status_code == 200, r.text
    m.assert_called_once()
    assert r.json()["fonts"][0]["family"] == "Inter"


async def test_fonts_search_unavailable_503(authed_client):
    with patch("app.api.fonts.search_fonts", side_effect=RuntimeError("no net")):
        r = await authed_client.get(
            "/api/fonts/search?q=x", headers={"x-api-key": "test-key"}
        )
    assert r.status_code == 503
    assert "Google Fonts unavailable" in r.json()["detail"]


async def test_fonts_default_returns_curated_set(authed_client):
    fake = [
        {"family": "Inter", "category": "sans-serif", "variants": ["regular"]},
        {"family": "Playfair Display", "category": "serif", "variants": ["regular"]},
    ]
    with patch("app.api.fonts.default_fonts", return_value=fake) as m:
        r = await authed_client.get(
            "/api/fonts/default", headers={"x-api-key": "test-key"}
        )
    assert r.status_code == 200, r.text
    m.assert_called_once()
    assert r.json()["fonts"][0]["family"] == "Inter"
