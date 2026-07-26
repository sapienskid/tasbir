"""Tests for the background generation service."""

from app.services.backgrounds import generate_background, GRADIENT_PRESETS, PATTERN_PRESETS


def test_gradient_presets_exist():
    assert len(GRADIENT_PRESETS) >= 6
    assert "sunset" in GRADIENT_PRESETS
    assert "ocean" in GRADIENT_PRESETS


def test_pattern_presets_exist():
    assert len(PATTERN_PRESETS) >= 4
    assert "dots" in PATTERN_PRESETS
    assert "grid" in PATTERN_PRESETS


def test_generate_energetic_background():
    bg = generate_background(content_type="article", mood="energetic")
    assert bg.name
    assert bg.css


def test_generate_professional_background():
    bg = generate_background(content_type="article", mood="professional")
    assert bg.name
    assert bg.css


def test_generate_quote_background():
    bg = generate_background(content_type="quote", mood="calm")
    assert bg.name
    assert bg.css
    assert "background" in bg.css


def test_generate_background_follows_user_brand_colors():
    brand_primary = "#ff1122"
    brand_secondary = "#334455"
    bg = generate_background(
        content_type="article",
        mood="sunset",
        brand_primary=brand_primary,
        brand_secondary=brand_secondary,
    )
    assert brand_primary in bg.css
    assert brand_secondary in bg.css
