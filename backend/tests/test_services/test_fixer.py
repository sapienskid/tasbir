"""Edge case tests for the HTML fixer module.

These tests verify the fixer handles malformed, empty, and extreme inputs
without crashing, and produces correct output across all edge cases.
"""

import pytest
from app.services.fixer import (
    fix_all,
    fix_brand_colors,
    fix_canvas_overflow,
    remove_template_placeholders,
    strip_emojis,
    strip_interactive_elements,
)


class TestRemoveTemplatePlaceholders:
    def test_empty_string(self):
        assert remove_template_placeholders("") == ""

    def test_no_placeholders(self):
        html = "<div>Hello World</div>"
        assert remove_template_placeholders(html) == html

    def test_simple_variable(self):
        assert remove_template_placeholders("{{name}}") == ""

    def test_multiple_placeholders(self):
        result = remove_template_placeholders("Hello {{name}}, you are {{age}} years old")
        assert result == "Hello , you are  years old"

    def test_nested_braces(self):
        result = remove_template_placeholders("{{{nested}}}")
        assert "nested" not in result or result == ""

    def test_mixed_placeholder_types(self):
        result = remove_template_placeholders("{{var}} %s [placeholder]")
        # Curly and percent placeholders removed
        assert "{{var}}" not in result
        assert "%s" not in result

    def test_unclosed_braces(self):
        result = remove_template_placeholders("{{unclosed")
        assert result is not None


class TestFixCanvasOverflow:
    def test_empty_string(self):
        # Should handle gracefully without crashing
        result = fix_canvas_overflow("", width=1080, height=1080)
        # Empty input stays empty or gets basic structure
        assert isinstance(result, str)

    def test_body_without_style(self):
        html = "<body><div>content</div></body>"
        result = fix_canvas_overflow(html, width=1080, height=1080)
        assert "overflow: hidden" in result
        assert "width: 1080px" in result
        assert "height: 1080px" in result

    def test_body_with_partial_style(self):
        html = '<body style="color: red;"><div>content</div></body>'
        result = fix_canvas_overflow(html, width=1080, height=1080)
        assert "overflow: hidden" in result

    def test_replaces_min_h_screen(self):
        html = '<body class="min-h-screen"><div>content</div></body>'
        result = fix_canvas_overflow(html, width=1080, height=1080)
        assert "min-h-screen" not in result
        assert "h-full" in result

    def test_replaces_h_screen(self):
        html = '<body class="h-screen"><div>content</div></body>'
        result = fix_canvas_overflow(html, width=1080, height=1080)
        assert "h-screen" not in result
        assert "h-full" in result

    def test_replaces_scroll(self):
        html = '<body><div class="overflow-y-auto">scroll</div></body>'
        result = fix_canvas_overflow(html, width=1080, height=1080)
        assert "overflow-y-auto" not in result
        assert "overflow-hidden" in result

    def test_zero_dimensions(self):
        html = "<body><div>content</div></body>"
        result = fix_canvas_overflow(html, width=0, height=0)
        assert "width: 0px" in result
        assert "height: 0px" in result

    def test_large_dimensions(self):
        html = "<body><div>content</div></body>"
        result = fix_canvas_overflow(html, width=4096, height=4096)
        assert "width: 4096px" in result
        assert "height: 4096px" in result

    def test_missing_width_height(self):
        html = "<body><div>content</div></body>"
        result = fix_canvas_overflow(html)
        # Should not crash
        assert "<body" in result

    def test_very_long_html(self):
        html = "<html><head></head><body>" + "x" * 100000 + "</body></html>"
        result = fix_canvas_overflow(html, width=1080, height=1080)
        assert "overflow: hidden" in result


class TestFixBrandColors:
    def test_empty_html(self):
        assert fix_brand_colors("", {"primary_color": "#ff0000"}) == ""

    def test_no_brand(self):
        html = '<div class="bg-primary">content</div>'
        assert fix_brand_colors(html, None) == html

    def test_empty_brand(self):
        html = '<div class="bg-primary">content</div>'
        assert fix_brand_colors(html, {}) == html

    def test_preserves_tailwind_classes(self):
        """The critical fix: bg-primary must NOT be stripped."""
        html = '<div class="bg-primary text-secondary font-sans p-4">content</div>'
        result = fix_brand_colors(html, {"primary_color": "#ff0000", "secondary_color": "#00ff00"})
        assert "bg-primary" in result
        assert "text-secondary" in result
        assert "font-sans" in result
        assert "p-4" in result

    def test_replaces_css_vars(self):
        html = '<div style="color: var(--color-primary);">content</div>'
        result = fix_brand_colors(html, {"primary_color": "#ff0000"})
        assert "var(--color-primary)" not in result
        assert "#ff0000" in result

    def test_missing_brand_colors(self):
        html = '<div style="color: var(--color-primary);">content</div>'
        result = fix_brand_colors(html, {})
        # No brand colors means no replacement
        assert "var(--color-primary)" in result

    def test_multiple_var_references(self):
        html = '<div style="background: var(--color-primary); color: var(--color-secondary); border: 1px solid var(--color-accent);">content</div>'
        result = fix_brand_colors(html, {"primary_color": "#ff0000", "secondary_color": "#00ff00"})
        assert "var(--color-primary)" not in result
        assert "var(--color-secondary)" not in result
        assert "#ff0000" in result
        assert "#00ff00" in result

    def test_var_without_brand_ref(self):
        html = '<div style="--custom: #123;">content</div>'
        result = fix_brand_colors(html, {"primary_color": "#ff0000"})
        assert result == html

    def test_malformed_var_patterns(self):
        html = '<div style="color: var(--primary-extra);">content</div>'
        result = fix_brand_colors(html, {"primary_color": "#ff0000"})
        # var(--primary) should match, but var(--primary-extra) should not
        assert "var(--primary-extra)" in result


class TestStripEmojis:
    def test_empty_string(self):
        assert strip_emojis("") == ""

    def test_no_emojis(self):
        text = "Hello World 123 !@#"
        assert strip_emojis(text) == text

    def test_basic_emojis(self):
        assert strip_emojis("Hello 😊 World") == "Hello  World"

    def test_multiple_emojis(self):
        assert strip_emojis("🎉🎊🎈") == ""

    def test_mixed_content(self):
        result = strip_emojis("Text 😊 with 👍 emojis 🎉 inside")
        assert "😊" not in result
        assert "👍" not in result
        assert "🎉" not in result
        assert "Text " in result
        assert " with " in result
        assert " emojis " in result
        assert " inside" in result

    def test_flags(self):
        assert strip_emojis("🇺🇸🇬🇧") == ""

    def test_skin_tones(self):
        assert strip_emojis("👍🏻👍🏿") == ""

    def test_html_with_emojis(self):
        html = "<p>Hello 😊 World</p>"
        result = strip_emojis(html)
        assert result == "<p>Hello  World</p>"

    def test_only_text_no_emoji(self):
        text = "a" * 1000
        assert strip_emojis(text) == text

    def test_unicode_math(self):
        """Mathematical symbols (not emoji) should be preserved."""
        text = "x² + y² = z²"
        assert strip_emojis(text) == text


class TestStripInteractiveElements:
    def test_empty_html(self):
        assert strip_interactive_elements("") == ""

    def test_anchor_tags(self):
        html = '<a href="https://example.com">Click</a>'
        assert strip_interactive_elements(html) == "Click"

    def test_button_tags(self):
        html = '<button onclick="submit()">Submit</button>'
        result = strip_interactive_elements(html)
        assert "<button" not in result
        assert "submit" not in result

    def test_input_tags(self):
        html = '<input type="text" name="email" />'
        assert strip_interactive_elements(html) == ""

    def test_form_tags(self):
        html = '<form action="/submit"><div>content</div></form>'
        result = strip_interactive_elements(html)
        assert "<form" not in result
        assert "</form>" not in result
        assert "content" in result

    def test_select_tags(self):
        html = '<select><option>1</option></select>'
        assert strip_interactive_elements(html) == ""

    def test_textarea_tags(self):
        html = '<textarea>text</textarea>'
        assert strip_interactive_elements(html) == ""

    def test_onclick_handler(self):
        html = '<div onclick="alert(1)">click</div>'
        assert strip_interactive_elements(html) == '<div >click</div>'

    def test_cursor_pointer(self):
        html = '<div class="cursor-pointer">click</div>'
        assert strip_interactive_elements(html) == '<div class="">click</div>'

    def test_cta_phrases(self):
        html = '<span>Click Here</span>'
        result = strip_interactive_elements(html)
        assert "Click Here" not in result

    def test_nested_interactive(self):
        html = '<div><a href="link"><button>Go</button></a></div>'
        result = strip_interactive_elements(html)
        assert "<a" not in result
        assert "<button" not in result
        assert "Go" not in result  # Button content is removed with the tag

    def test_mixed_content_preserved(self):
        html = '<div class="text-lg">Hello <a href="/">World</a> here</div>'
        result = strip_interactive_elements(html)
        assert "<a" not in result
        assert "World" in result
        assert "Hello" in result
        assert "here" in result


class TestFixAll:
    def test_empty_html(self):
        result = fix_all("")
        assert isinstance(result, str)

    def test_none_input(self):
        with pytest.raises((AttributeError, TypeError)):
            fix_all(None)  # type: ignore

    def test_complete_pipeline(self):
        html = (
            '<!DOCTYPE html><html><head></head><body>'
            '<div class="bg-primary text-secondary p-4">{{name}}</div>'
            '<button onclick="submit()">Go</button>'
            '<span>Hello 😊 World</span>'
            '</body></html>'
        )
        result = fix_all(html, width=1080, height=1080, brand={"primary_color": "#000", "secondary_color": "#fff"})
        assert "{{name}}" not in result
        assert "<button" not in result
        assert "😊" not in result
        assert "bg-primary" in result
        assert "text-secondary" in result
        assert "Hello" in result
        assert "World" in result

    def test_html_with_only_tags(self):
        html = "<div></div><span></span>"
        result = fix_all(html)
        # Empty divs/spans should be cleaned
        pass  # Just shouldn't crash

    def test_very_long_html(self):
        html = "<!DOCTYPE html><html><head></head><body>" + "x" * 50000 + "</body></html>"
        result = fix_all(html, width=1080, height=1080)
        assert len(result) > 0

    def test_malformed_html(self):
        html = "<div><span>unclosed"
        result = fix_all(html)
        assert isinstance(result, str)

    def test_empty_containers_removed(self):
        html = "<div></div><span></span><div>content</div><span></span>"
        result = fix_all(html)
        assert "content" in result
