"""Tests for prompt registry and default prompt loading."""

import pytest
from app.agents.prompts.registry import DEFAULT_PROMPTS, get_prompt, list_prompts
from app.agents.prompts.copywriter import COPYWRITER_SYSTEM_PROMPT
from app.agents.prompts.designer import DESIGNER_SYSTEM_PROMPT
from app.agents.prompts.quality_check import QUALITY_CHECK_SYSTEM_PROMPT
from app.agents.prompts.strategist import STRATEGIST_SYSTEM_PROMPT
from app.agents.prompts.visual_director import VISUAL_DIRECTOR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_default_prompts_exist():
    expected_agents = [
        "strategist",
        "copywriter",
        "visual_director",
        "designer",
        "quality_check",
        "token_generator",
    ]
    for agent in expected_agents:
        assert agent in DEFAULT_PROMPTS
        prompt = await get_prompt(agent)
        assert prompt.system_prompt is not None
        assert len(prompt.system_prompt) > 100


@pytest.mark.asyncio
async def test_strategist_prompt_persona():
    # Test the Python constant directly — DB may have an older seeded version
    assert "Aura Vance" in STRATEGIST_SYSTEM_PROMPT
    assert "Creative Director" in STRATEGIST_SYSTEM_PROMPT
    assert "ANONYMOUS" in STRATEGIST_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_copywriter_prompt_persona():
    prompt = await get_prompt("copywriter")
    assert "Julian Sterling" in prompt.system_prompt
    assert "HEADLINE" in prompt.system_prompt
    assert "HUMAN VOICE" in prompt.system_prompt
    assert "USER-ONLY BADGES" in prompt.system_prompt


@pytest.mark.asyncio
async def test_visual_director_prompt_persona():
    # Test the Python constant directly — DB may have an older seeded version
    assert "Elena Rostova" in VISUAL_DIRECTOR_SYSTEM_PROMPT
    assert "ANONYMOUS" in VISUAL_DIRECTOR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_designer_prompt_persona():
    prompt = await get_prompt("designer")
    assert "Marcus Chen" in prompt.system_prompt
    assert "BRAND LOGO INTEGRATION" in prompt.system_prompt
    assert "STRICT USER-ONLY BADGES" in prompt.system_prompt
    assert "<!DOCTYPE html>" in prompt.system_prompt


@pytest.mark.asyncio
async def test_quality_check_prompt_persona():
    # Test the Python constant directly — DB may have an older seeded version
    assert "Victoria Thorne" in QUALITY_CHECK_SYSTEM_PROMPT
    assert "Agent Name Leak" in QUALITY_CHECK_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_list_prompts():
    prompts = await list_prompts()
    assert len(prompts) >= 6


# ── Copywriter character limit enforcement ──────────────────────────────────

def test_copywriter_prompt_has_character_limits():
    """Copywriter prompt must explicitly enforce per-field character limits."""
    assert "50 characters" in COPYWRITER_SYSTEM_PROMPT
    assert "120 characters" in COPYWRITER_SYSTEM_PROMPT
    assert "40 characters" in COPYWRITER_SYSTEM_PROMPT
    assert "70 characters" in COPYWRITER_SYSTEM_PROMPT


def test_copywriter_prompt_bans_ai_tropes():
    """Copywriter prompt must ban AI clichés."""
    assert "Game-changing" in COPYWRITER_SYSTEM_PROMPT
    assert "Unleash" in COPYWRITER_SYSTEM_PROMPT
    assert "Seamlessly" in COPYWRITER_SYSTEM_PROMPT


def test_copywriter_validate_copy_fields_valid():
    from app.agents.orchestrator.nodes.copywriter import _validate_copy_fields
    valid = "HEADLINE: Test\nSUBHEAD: Test sub\nKEY POINTS: - Item\nBADGE: None\nTAGLINE: Test tag"
    assert _validate_copy_fields(valid) is True


def test_copywriter_validate_copy_fields_invalid():
    from app.agents.orchestrator.nodes.copywriter import _validate_copy_fields
    invalid = "HEADLINE: Test\nSUBHEAD: Test sub"
    assert _validate_copy_fields(invalid) is False


# ── Designer brand fonts and safe zones ────────────────────────────────────

def test_designer_prompt_has_brand_fonts_instruction():
    """Designer prompt must tell LLM to use brand fonts from context first."""
    assert "BRAND FONTS FIRST" in DESIGNER_SYSTEM_PROMPT
    assert "SAFE ZONES" in DESIGNER_SYSTEM_PROMPT
    assert "TEXT DENSITY" in DESIGNER_SYSTEM_PROMPT


def test_designer_prompt_has_mermaid_instruction():
    """Designer prompt must mention Mermaid diagram rendering."""
    assert "MERMAID" in DESIGNER_SYSTEM_PROMPT or "mermaid" in DESIGNER_SYSTEM_PROMPT


# ── Designer font extraction utilities ─────────────────────────────────────

def test_extract_brand_fonts_from_tokens():
    from app.agents.orchestrator.nodes.designer import _extract_brand_fonts
    tokens = {
        "fontFamily": {
            "heading": {"$value": "Playfair Display"},
            "body": {"$value": "Lato"},
        }
    }
    fonts = _extract_brand_fonts(tokens, {})
    assert fonts["heading"] == "Playfair Display"
    assert fonts["body"] == "Lato"


def test_extract_brand_fonts_fallback_to_defaults():
    from app.agents.orchestrator.nodes.designer import (
        _extract_brand_fonts,
        _DEFAULT_HEADING_FONT,
        _DEFAULT_BODY_FONT,
    )
    fonts = _extract_brand_fonts({}, {})
    assert fonts["heading"] == _DEFAULT_HEADING_FONT
    assert fonts["body"] == _DEFAULT_BODY_FONT


def test_extract_brand_fonts_from_brand_metadata():
    from app.agents.orchestrator.nodes.designer import _extract_brand_fonts
    brand = {"font_heading": "Merriweather", "font_body": "Open Sans"}
    fonts = _extract_brand_fonts({}, brand)
    assert fonts["heading"] == "Merriweather"
    assert fonts["body"] == "Open Sans"


def test_build_google_fonts_url_with_brand_fonts():
    from app.agents.orchestrator.nodes.designer import _build_google_fonts_url
    fonts = {"heading": "Playfair Display", "body": "Lato", "mono": "Fira Code"}
    url = _build_google_fonts_url(fonts)
    assert "fonts.googleapis.com" in url
    assert "Playfair+Display" in url
    assert "Lato" in url


def test_build_google_fonts_url_deduplicates():
    from app.agents.orchestrator.nodes.designer import _build_google_fonts_url
    # Same font used for heading and body — should appear only once
    fonts = {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"}
    url = _build_google_fonts_url(fonts)
    assert url.count("Inter") == 1


# ── Designer Mermaid and KaTeX injection ───────────────────────────────────

def test_inject_mermaid_when_detected():
    from app.agents.orchestrator.nodes.designer import _inject_mermaid
    content = "```mermaid\ngraph TD\nA-->B\n```"
    html = "<!DOCTYPE html><html><head></head><body></body></html>"
    result = _inject_mermaid(html, content)
    assert "mermaid" in result
    assert "data-mermaid-ready" in result


def test_inject_mermaid_not_added_without_content():
    from app.agents.orchestrator.nodes.designer import _inject_mermaid
    content = "No diagrams here, just plain text."
    html = "<!DOCTYPE html><html><head></head><body></body></html>"
    result = _inject_mermaid(html, content)
    assert result == html  # unchanged


def test_inject_katex_when_detected():
    from app.agents.orchestrator.nodes.designer import _inject_katex
    content = r"Here is some math: \(\frac{a}{b}\)"
    html = "<!DOCTYPE html><html><head></head><body></body></html>"
    result = _inject_katex(html, content)
    assert "katex" in result.lower()


def test_inject_google_fonts_replaces_existing():
    from app.agents.orchestrator.nodes.designer import _inject_google_fonts
    html = (
        '<!DOCTYPE html><html><head>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter&display=swap">'
        '</head><body></body></html>'
    )
    new_url = "https://fonts.googleapis.com/css2?family=Playfair+Display&display=swap"
    result = _inject_google_fonts(html, new_url)
    assert "Playfair+Display" in result
    # Old Inter-only link replaced
    assert result.count("fonts.googleapis.com") == 1
