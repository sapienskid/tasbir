"""Tests for HTML cleanup post-processing."""

from app.services.cleanup import clean_html, remove_emojis, strip_agent_names


def test_remove_emojis():
    text_with_emoji = "Hello world 🔥🚀😊 testing text"
    cleaned = remove_emojis(text_with_emoji)
    assert "🔥" not in cleaned
    assert "🚀" not in cleaned
    assert "😊" not in cleaned
    assert cleaned.strip() == "Hello world  testing text"


def test_clean_html_converts_buttons_and_strips_emojis():
    raw_html = (
        "<!DOCTYPE html><html><body>"
        "<button class='btn'>Click Me 🚀</button>"
        "<nav>Website Nav</nav>"
        "<h1>Headline Title 😊</h1>"
        "</body></html>"
    )
    cleaned = clean_html(raw_html)

    # Emojis stripped
    assert "🚀" not in cleaned
    assert "😊" not in cleaned

    # Button element converted to non-interactive callout span
    assert "<button" not in cleaned
    assert "pointer-events:none;" in cleaned

    # Website nav element stripped
    assert "<nav>" not in cleaned


def test_strip_agent_names_removes_all_personas():
    """All internal agent persona names must be stripped from output text."""
    text = (
        "Designed by Marcus Chen for Julian Sterling's brand campaign. "
        "Visual direction by Elena Rostova. Audited by Victoria Thorne. "
        "Tokens by Dr. Soren Lindqvist. Strategy: Aura Vance."
    )
    cleaned = strip_agent_names(text)
    for name in ["Marcus Chen", "Julian Sterling", "Elena Rostova",
                 "Victoria Thorne", "Soren Lindqvist", "Aura Vance"]:
        assert name not in cleaned, f"Persona name '{name}' was not stripped"


def test_clean_html_strips_agent_names_in_comments():
    """Agent persona names in HTML comments or visible text must be stripped."""
    raw_html = (
        "<!DOCTYPE html><html><body>"
        "<!-- Designed by Marcus Chen -->"
        "<p>Crafted by Julian Sterling</p>"
        "<span>Elena Rostova art direction</span>"
        "</body></html>"
    )
    cleaned = clean_html(raw_html)
    for name in ["Marcus Chen", "Julian Sterling", "Elena Rostova"]:
        assert name not in cleaned, f"Persona name '{name}' leaked into cleaned output"
