"""Designer output hardening tests — fallback HTML escapes copy fields."""

from app.agents.orchestrator.nodes.designer import _build_fallback_html
from app.services.formats import FormatInfo


def _fmt():
    return FormatInfo(id="instagram-square", name="", width=1080, height=1080)


def test_fallback_escapes_injected_script_in_headline():
    html = _build_fallback_html(
        _fmt(),
        {"headline": "</div><script>alert(1)</script>", "subhead": "", "body": "x",
         "tagline": "", "badge": None},
    )
    # Raw dangerous markup must never appear — only entity-encoded text.
    assert "<script>" not in html
    assert "</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_fallback_escapes_footer_and_category():
    html = _build_fallback_html(
        _fmt(),
        {"headline": "H", "subhead": "", "body": "x", "tagline": "", "badge": None},
        ground="white",
        category='WRITING"><img src=x onerror=alert(1)>',
        footer_left='A" onmouseover="alert(1)',
        footer_right="@x",
    )
    # No real tag or attribute can be forged through the copy fields.
    assert "<img" not in html
    assert 'onerror="' not in html
    assert 'onmouseover="' not in html


def test_fallback_keeps_normal_text():
    html = _build_fallback_html(
        _fmt(),
        {"headline": "Hello World", "subhead": "Sub", "body": "Body text",
         "tagline": "Tag", "badge": None},
    )
    assert "Hello World" in html
    assert "Sub" in html
    assert "Body text" in html
