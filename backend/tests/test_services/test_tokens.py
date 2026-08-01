"""Tests for design token loading and HTML injection."""

from pathlib import Path

from app.services.tokens import (
    load_tokens,
    DEFAULT_TOKEN_VALUES,
    inject_tokens_into_html,
    build_css_var_reference,
    load_brand_design,
    category_matches,
    resolve_ground,
    DEFAULT_CATEGORIES,
)
from app.agents.orchestrator.nodes.designer import _build_fallback_html
from app.agents.orchestrator.nodes.quality_check import _run_deterministic_checks


def test_load_tokens_defaults(tmp_path: Path):
    tokens = load_tokens(tmp_path / "non_existent.yaml")
    assert "--color-bg" in tokens
    assert tokens["--color-bg"] == "#FFFFFF"


def test_load_tokens_from_file(tmp_path: Path):
    tf = tmp_path / "tokens.yaml"
    tf.write_text("--color-bg: '#ff0000'")
    tokens = load_tokens(tf)
    assert tokens["--color-bg"] == "#ff0000"


def test_inject_tokens_into_html():
    html = "<html><head></head><body><h1>Hi</h1></body></html>"
    tokens = {"--color-bg": "#0f172a"}
    res = inject_tokens_into_html(html, tokens)
    assert "--color-bg: #0f172a;" in res
    assert "<style>" in res


def test_inject_tokens_preserves_designer_styles_next_to_root():
    """When a designer puts :root + real styles in one <style> block, only the
    :root rule is stripped — the real CSS must survive token injection."""
    html = (
        '<html><head><style>'
        ":root { --color-bg: #111111; --color-text: #eeeeee; }"
        "body { width: 1080px; height: 1080px; color: var(--color-text); }"
        ".headline { font-size: 68px; font-weight: 700; }"
        '</style></head><body><div class="headline">Hi</div></body></html>'
    )
    res = inject_tokens_into_html(html, {"--color-bg": "#FFFFFF", "--color-text": "#000000"})
    # designer's real styles survive
    assert ".headline" in res and "font-size: 68px" in res
    assert "body { width: 1080px" in res
    # designer's :root rule is gone, system's injected block is present
    assert ":root { --color-bg: #111111;" not in res
    assert "--color-bg: #FFFFFF;" in res


def test_default_tokens_are_monochrome():
    """The default palette must be strictly grayscale — no hue."""
    colors = {
        DEFAULT_TOKEN_VALUES.get("--color-bg", ""),
        DEFAULT_TOKEN_VALUES.get("--color-bg-inverted", ""),
        DEFAULT_TOKEN_VALUES.get("--color-text", ""),
        DEFAULT_TOKEN_VALUES.get("--color-text-inverted", ""),
        DEFAULT_TOKEN_VALUES.get("--color-text-secondary", ""),
        DEFAULT_TOKEN_VALUES.get("--color-text-tertiary", ""),
        DEFAULT_TOKEN_VALUES.get("--color-border", ""),
        DEFAULT_TOKEN_VALUES.get("--color-border-inverted", ""),
    }
    assert colors == {
        "#FFFFFF", "#000000", "#6E6E6E", "#B0B0B0",
        "#D9D9D9", "#2A2A2A",
    }


def test_css_var_reference_has_semantic_roles_not_values():
    ref = build_css_var_reference(DEFAULT_TOKEN_VALUES)
    assert "--color-bg" in ref
    # Never leak hex values into the prompt reference
    assert "#" not in ref
    assert "white" in ref.lower() or "black" in ref.lower()


def test_load_brand_design_defaults(tmp_path: Path):
    bd = load_brand_design(tmp_path / "missing.yaml")
    assert set(bd["footer"].keys()) == {"left", "right"}
    assert bd["categories"]


def test_category_matches_issue_placeholder():
    assert category_matches("NOTE", DEFAULT_CATEGORIES)
    assert category_matches("THE LIMITS No.12", DEFAULT_CATEGORIES)
    assert not category_matches("THE LIMITS No.x", DEFAULT_CATEGORIES)
    assert not category_matches("INVENTED", DEFAULT_CATEGORIES)


def test_resolve_ground_priority():
    # campaign beats category
    assert resolve_ground({"ground": "black"}, "WRITING", DEFAULT_CATEGORIES) == "black"
    # category ground (NOTE → black) applies when campaign doesn't specify
    assert resolve_ground({}, "NOTE", DEFAULT_CATEGORIES) == "black"
    # default is white
    assert resolve_ground({}, "WRITING", DEFAULT_CATEGORIES) == "white"


def test_fallback_html_is_monochrome_and_swiss():
    fmt = type("F", (), {"width": 1080, "height": 1080})()
    fb = _build_fallback_html(
        fmt,
        {"headline": "Hi", "subhead": "", "body": "Body", "tagline": "", "badge": None},
        category="NOTE",
        footer_left="SABIN POKHAREL",
        footer_right="@SAPIENSKID",
    )
    # Uses CSS variables — no hardcoded hex
    assert "var(--color-bg)" in fb
    assert "#" not in fb.replace("<!DOCTYPE", "")
    # Has category label and footer
    assert "NOTE" in fb
    assert "SABIN POKHAREL" in fb
    assert "@SAPIENSKID" in fb


def test_deterministic_checks_pass_on_clean_html():
    html = ('<html><head><style>body{width:1080px;height:1080px;background:var(--color-bg)}</style></head>'
            '<body style="width:1080px;height:1080px"><div class="kicker">WRITING</div>'
            '<div>SABIN POKHAREL</div><div>@X</div></body></html>')
    issues = _run_deterministic_checks(html, {"left": "SABIN POKHAREL", "right": "@X"}, "WRITING", 1080, 1080)
    assert issues == []


def test_deterministic_checks_accept_css_body_sizing():
    """Canvas size may be defined in a CSS body rule, not just inline."""
    html = ('<html><head><style>body{width:1200px;height:675px;background:var(--color-bg)}</style></head>'
            '<body><div class="kicker">WRITING</div><span>SABIN POKHAREL</span><span>@X</span></body></html>')
    issues = _run_deterministic_checks(html, {"left": "SABIN POKHAREL", "right": "@X"}, "WRITING", 1200, 675)
    assert issues == []


def test_deterministic_checks_accept_whitespace_in_css():
    """Canvas size written as 'width: 1080px' (space after colon) is valid."""
    html = ('<html><head><style>body { width: 1080px; height: 1080px; background: var(--color-bg); }</style></head>'
            '<body><div class="kicker">WRITING</div><span>SABIN POKHAREL</span><span>@X</span></body></html>')
    issues = _run_deterministic_checks(html, {"left": "SABIN POKHAREL", "right": "@X"}, "WRITING", 1080, 1080)
    assert issues == []


def test_deterministic_checks_catch_violations():
    html = '<html><style>body{width:1080px;height:1080px;color:#ff0000}</style><body>text 😀</body></html>'
    issues = _run_deterministic_checks(html, {"left": "SABIN POKHAREL", "right": "@X"}, "WRITING", 1080, 1080)
    joined = "; ".join(issues)
    assert "hex color" in joined
    assert "Emoji" in joined
    assert "WRITING" in joined  # category missing
    assert "SABIN POKHAREL" in joined  # footer missing


def test_deterministic_checks_ignore_designer_root_block():
    """A designer :root block is stripped by the token injector before render,
    so hex inside it is harmless and must not be flagged."""
    html = ('<html><head><style>:root { --color-bg: #000000; --color-text: #FFFFFF; }'
            'body{width:1080px;height:1080px;background:var(--color-bg)}</style></head>'
            '<body style="width:1080px;height:1080px"><div class="kicker">WRITING</div>'
            '<span>SABIN POKHAREL</span><span>@X</span></body></html>')
    issues = _run_deterministic_checks(html, {"left": "SABIN POKHAREL", "right": "@X"}, "WRITING", 1080, 1080)
    assert issues == []


def test_deterministic_checks_require_style_block():
    """HTML without a <style> block is degenerate and must be flagged."""
    html = '<html><head></head><body style="width:1080px;height:1080px"><div>WRITING</div><span>SABIN POKHAREL</span><span>@X</span></body></html>'
    issues = _run_deterministic_checks(html, {"left": "SABIN POKHAREL", "right": "@X"}, "WRITING", 1080, 1080)
    assert any("style" in i.lower() for i in issues)


def test_deterministic_checks_require_canvas_size():
    """The canvas width/height must be defined somewhere in the HTML."""
    html = ('<html><head><style>body{background:var(--color-bg)}</style></head>'
            '<body><div>WRITING</div></body></html>')
    issues = _run_deterministic_checks(html, {"left": "", "right": ""}, "WRITING", 1080, 1080)
    assert any("canvas" in i.lower() or "width:" in i.lower() for i in issues)
