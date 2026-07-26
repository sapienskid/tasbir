"""Tests for HTML cleanup post-processing."""

from app.services.cleanup import clean_html, remove_emojis


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
