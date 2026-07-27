"""Edge case tests for DTCG token exchange.

Tests extreme or malformed token configurations that should not crash.
"""

import pytest
from app.services.token_exchange import (
    _flatten,
    _resolve_ref,
    _resolve_tree,
    _inject_defaults,
    _merge_brand_into_tokens,
    tokens_to_tailwind_config,
    tokens_to_css_variables,
    build_config_html,
    flatten_tokens,
    build_dtcg,
)


class TestFlattenEdgeCases:
    def test_empty_dict(self):
        assert _flatten({}) == {}
        assert flatten_tokens({}) == {}

    def test_none_value(self):
        result = _flatten({"key": None})  # type: ignore
        assert isinstance(result, dict)

    def test_nested_empty_dicts(self):
        tokens = {"a": {"b": {}}}
        assert _flatten(tokens) == {}

    def test_deeply_nested_single_path(self):
        tokens = {"a": {"b": {"c": {"d": {"$value": "deep"}}}}}
        result = _flatten(tokens)
        assert "a/b/c/d" in result
        assert result["a/b/c/d"] == "deep"

    def test_deeply_nested_no_value(self):
        tokens = {"a": {"b": {"c": {"d": {}}}}}
        assert _flatten(tokens) == {}

    def test_mixed_types(self):
        tokens = {
            "color": {"$value": "#000", "$type": "color"},
            "font": {"family": {"$value": "Inter"}},
        }
        result = _flatten(tokens)
        assert result["color"] == "#000"
        assert result["font/family"] == "Inter"

    def test_very_large_token_set(self):
        tokens = {}
        for i in range(1000):
            tokens[f"token{i}"] = {"$value": str(i)}
        result = _flatten(tokens)
        assert len(result) == 1000

    def test_unicode_keys(self):
        tokens = {"café": {"$value": "value"}}
        result = _flatten(tokens)
        assert "café" in result


class TestResolveRefEdgeCases:
    def test_non_ref_value(self):
        tree = {"color": {"primary": {"$value": "#000"}}}
        assert _resolve_ref("plain text", tree) == "plain text"

    def test_valid_ref(self):
        tree = {"color": {"primary": {"$value": "#000"}}}
        assert _resolve_ref("{color.primary}", tree) == "#000"

    def test_nested_ref(self):
        tree = {
            "color": {"brand": {"$value": "#00f"}},
            "text": {"primary": {"$value": "{color.brand}"}},
        }
        result = _resolve_ref("{text.primary}", tree)
        assert result == "#00f"

    def test_broken_ref_returns_fallback(self):
        tree = {"color": {"primary": {"$value": "#000"}}}
        result = _resolve_ref("{color.missing}", tree)
        assert result.startswith("#")  # Returns fallback hex

    def test_empty_ref(self):
        tree = {"color": {"primary": {"$value": "#000"}}}
        result = _resolve_ref("{}", tree)
        assert result is not None

    def test_deeply_nested_ref(self):
        tree = {
            "a": {"b": {"c": {"d": {"e": {"$value": "deep"}}}}},
            "ref": {"$value": "{a.b.c.d.e}"},
        }
        assert _resolve_ref("{ref}", tree) == "deep"

    def test_self_reference(self):
        """Self-referencing tokens should not cause infinite loop."""
        tree = {"self": {"$value": "{self}"}}
        result = _resolve_ref("{self}", tree)
        assert not result.startswith("{")  # Should resolve to fallback


class TestTokensToTailwindConfigEdgeCases:
    def test_empty_tokens(self):
        result = tokens_to_tailwind_config({})
        assert result == {}

    def test_none_input(self):
        with pytest.raises((AttributeError, TypeError)):
            tokens_to_tailwind_config(None)  # type: ignore

    def test_single_color(self):
        tokens = {"color": {"primary": {"$value": "#ff0000"}}}
        result = tokens_to_tailwind_config(tokens)
        assert "colors" in result
        assert result["colors"].get("primary") == "#ff0000"

    def test_color_with_group_prefix(self):
        """DTCG groups like tasbir/color/primary should still be parsed."""
        dtcg = build_dtcg({"tasbir/color/primary": "#ff0000"})
        result = tokens_to_tailwind_config(dtcg)
        assert "colors" in result
        assert result["colors"].get("primary") == "#ff0000"

    def test_deeply_nested_color(self):
        dtcg = {"tasbir": {"color": {"palette": {"brand": {"$value": "#333"}}}}}
        result = tokens_to_tailwind_config(dtcg)
        # Should use last segment as token name
        assert "colors" in result
        assert result["colors"].get("brand") == "#333"

    def test_font_family_as_list(self):
        tokens = {"fontFamily": {"sans": {"$value": "Inter, system-ui"}}}
        result = tokens_to_tailwind_config(tokens)
        assert "fontFamily" in result
        assert isinstance(result["fontFamily"]["sans"], list)

    def test_font_family_as_single(self):
        tokens = {"fontFamily": {"mono": {"$value": "JetBrains Mono"}}}
        result = tokens_to_tailwind_config(tokens)
        assert isinstance(result["fontFamily"]["mono"], list)
        assert result["fontFamily"]["mono"][0] == "JetBrains Mono"

    def test_unknown_category_ignored(self):
        tokens = {"unknownCat": {"whatever": {"$value": "val"}}}
        result = tokens_to_tailwind_config(tokens)
        assert result == {}

    def test_opacity_as_string(self):
        tokens = {"opacity": {"half": {"$value": "0.5"}}}
        result = tokens_to_tailwind_config(tokens)
        assert result["opacity"]["half"] == "0.5"


class TestCssVariablesEdgeCases:
    def test_empty_tokens(self):
        assert tokens_to_css_variables({}) == ""

    def test_none_input(self):
        with pytest.raises((AttributeError, TypeError)):
            tokens_to_css_variables(None)  # type: ignore

    def test_single_variable(self):
        tokens = {"color": {"primary": {"$value": "#000"}}}
        result = tokens_to_css_variables(tokens)
        assert ":root" in result
        assert "--color-primary: #000;" in result

    def test_multiple_categories(self):
        tokens = {
            "color": {"primary": {"$value": "#000"}, "secondary": {"$value": "#fff"}},
            "spacing": {"md": {"$value": "1rem"}},
        }
        result = tokens_to_css_variables(tokens)
        assert "--color-primary: #000;" in result
        assert "--color-secondary: #fff;" in result
        assert "--spacing-md: 1rem;" in result

    def test_special_chars_in_values(self):
        tokens = {"shadow": {"lg": {"$value": "0 10px 15px -3px rgba(0,0,0,0.1)"}}}
        result = tokens_to_css_variables(tokens)
        assert "--shadow-lg" in result


class TestMergeBrandIntoEdgeCases:
    def test_empty_tokens_and_brand(self):
        result = _merge_brand_into_tokens({}, {})
        assert isinstance(result, dict)

    def test_none_tokens(self):
        result = _merge_brand_into_tokens(None, None)  # type: ignore
        assert isinstance(result, dict)

    def test_brand_does_not_override_tokens(self):
        """Brand metadata does NOT override user tokens — colors come from tokens only."""
        tokens = {"color": {"primary": {"$value": "#000"}}}
        brand = {"primary_color": "#fff"}
        result = _merge_brand_into_tokens(tokens, brand)
        assert result["color"]["primary"]["$value"] == "#000"

    def test_brand_secondary_not_added_without_tokens(self):
        """Brand colors are NOT injected — they must come from the token set itself."""
        result = _merge_brand_into_tokens({}, {"primary_color": "#f00"})
        assert "color" not in result or "primary" not in result.get("color", {})

    def test_defaults_for_missing_categories(self):
        """_inject_defaults must run after merge."""
        result = _merge_brand_into_tokens({}, {})
        # After dead-code fix, defaults should be present
        assert "fontFamily" in result
        assert "spacing" in result
        assert "borderRadius" in result

    def test_merge_preserves_existing_fonts(self):
        tokens = {"fontFamily": {"display": {"$value": "Custom"}}}
        result = _merge_brand_into_tokens(tokens, {})
        assert result["fontFamily"]["display"]["$value"] == "Custom"


class TestBuildConfigHtmlEdgeCases:
    def test_empty_tokens(self):
        result = build_config_html({}, {})
        assert len(result) > 100
        assert "tailwindcss" in result or "color" in result.lower()

    def test_none_tokens(self):
        result = build_config_html(None, None)  # type: ignore
        assert "tailwindcss" in result or "color" in result.lower()

    def test_google_fonts_included(self):
        result = build_config_html({}, {})
        assert "fonts.googleapis.com" in result

    def test_css_vars_included(self):
        tokens = {"color": {"primary": {"$value": "#ff0000"}}}
        result = build_config_html(tokens, {})
        assert "<style>" in result
        assert "--color-primary" in result

    def test_config_contains_theme_vars(self):
        result = build_config_html({"color": {"primary": {"$value": "#f00"}}}, {})
        assert "--color-primary: #f00" in result
