"""Tests for the DTCG token exchange service."""

from app.services.token_exchange import flatten_tokens, build_dtcg, tokens_to_tailwind_config


def test_flatten_nested_tokens():
    dtcg = {
        "tasbir": {
            "color": {
                "$type": "color",
                "primary": {"$value": "#0066cc"},
                "surface": {"$value": "#ffffff"},
            }
        }
    }
    flat = flatten_tokens(dtcg)
    assert "tasbir/color/primary" in flat
    assert flat["tasbir/color/primary"] == "#0066cc"
    assert flat["tasbir/color/surface"] == "#ffffff"


def test_flatten_empty():
    assert flatten_tokens({}) == {}


def test_build_dtcg_from_flat():
    flat = {"tasbir/color/primary": "#0066cc"}
    result = build_dtcg(flat)
    assert "tasbir" in result
    assert result["tasbir"]["color"]["primary"]["$value"] == "#0066cc"


def test_tokens_to_tailwind_config():
    flat = {"tasbir/color/primary": "#0066cc", "tasbir/color/surface": "#ffffff"}
    dtcg = build_dtcg(flat)
    tw = tokens_to_tailwind_config(dtcg)
    assert "colors" in tw
    assert tw["colors"].get("primary") == "#0066cc"
    assert tw["colors"].get("surface") == "#ffffff"
