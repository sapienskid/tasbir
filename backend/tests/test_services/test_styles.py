"""Phase 1 — design-language presets: styles, DI normalization, style rules."""

from __future__ import annotations

from app.services.design_instruction import (
    format_design_instruction_block,
    pick_layout_archetype,
)
from app.services.styles import (
    STYLE_LANGUAGES,
    STYLE_PRESETS,
    accent_tokens_for,
    apply_style_preset,
    build_style_rules_block,
    media_director_guidance,
    normalize_design_instruction,
    style_labels,
)


def test_presets_are_complete():
    assert STYLE_LANGUAGES[0] == "swiss-editorial"
    for lang in STYLE_LANGUAGES:
        p = STYLE_PRESETS[lang]
        assert p["label"]
        assert p["media_policy"] in ("photo-forward", "illustration-forward", "typographic")
        assert isinstance(p["emoji"], bool)
        assert isinstance(p["grayscale"], bool)
        assert isinstance(p["accent"], bool)
        assert "palette_rules" in p and "media_guide" in p and "di" in p
        assert p["di"]["style"]["emoji"] == p["emoji"]
        assert p["di"]["do_dont"]["do"] and p["di"]["do_dont"]["dont"]
        assert p["di"]["layout_archetypes"]


def test_swiss_default_matches_current_behaviour():
    di = apply_style_preset("swiss-editorial", {})
    assert di["style_language"] == "swiss-editorial"
    assert di["style"]["emoji"] is False
    assert di["photo"]["grayscale"] is True
    assert di["photo"]["media_policy"] == "photo-forward"
    assert di["style"]["accent"] == "none"


def test_apply_preset_preserves_structural_fields():
    base = {"spacing": {"margin": 40}, "type_scale": {"roles": {"headline": {"size": 60}}}}
    di = apply_style_preset("vibrant-pop", base)
    # Structural fields survive.
    assert di["spacing"]["margin"] == 40
    assert di["type_scale"]["roles"]["headline"]["size"] == 60
    # Language fields come from the preset.
    assert di["style_language"] == "vibrant-pop"
    assert di["style"]["emoji"] is True
    assert di["photo"]["grayscale"] is False
    assert di["photo"]["media_policy"] == "illustration-forward"
    assert di["style"]["accent"] == "accent"


def test_unknown_language_falls_back_to_swiss():
    di = apply_style_preset("nope", {})
    assert di["style_language"] == "swiss-editorial"


def test_accent_tokens_defaults():
    assert accent_tokens_for("swiss-editorial") == {}
    assert "--color-accent" in accent_tokens_for("vibrant-pop")
    assert "--color-accent-secondary" in accent_tokens_for("vibrant-pop")


def test_normalize_fills_missing_fields():
    di = normalize_design_instruction({"style": {}})
    assert di["style_language"] == "swiss-editorial"
    assert di["style"]["emoji"] is False
    assert di["photo"]["grayscale"] is True
    assert di["photo"]["media_policy"] == "photo-forward"
    # Existing values win.
    di2 = normalize_design_instruction(
        {"style": {"emoji": True}, "photo": {"grayscale": False}}
    )
    assert di2["style"]["emoji"] is True
    assert di2["photo"]["grayscale"] is False


def test_style_rules_block_reflects_language():
    swiss = build_style_rules_block(apply_style_preset("swiss-editorial", {}))
    assert "Emoji: FORBIDDEN" in swiss
    assert "photos render grayscale" in swiss
    vibrant = build_style_rules_block(apply_style_preset("vibrant-pop", {}))
    assert "Emoji: ALLOWED" in vibrant
    assert "photos render full color" in vibrant
    assert "var(--color-accent)" in vibrant


def test_media_director_guidance_reflects_language():
    assert "grayscale" in media_director_guidance(apply_style_preset("swiss-editorial", {}))
    assert "full color" in media_director_guidance(apply_style_preset("bold-modern", {}))
    assert "emoji are allowed" in media_director_guidance(
        apply_style_preset("vibrant-pop", {})
    )


def test_di_block_uses_style_rules_for_vibrant():
    di = apply_style_preset("vibrant-pop", {})
    block = format_design_instruction_block(di)
    assert "VIBRANT POP" in block.upper()
    assert "Emoji: ALLOWED" in block
    assert "var(--color-accent)" in block


def test_pick_archetype_uses_per_style_pool():
    di = apply_style_preset("vibrant-pop", {})
    archs = set()
    for i in range(40):
        key, _ = pick_layout_archetype(di, f"title {i}|square")
        archs.add(key)
    assert archs and archs <= set(di["layout_archetypes"].keys())
    assert "pop-hero" in di["layout_archetypes"]
    assert "editorial-stack" not in di["layout_archetypes"]


def test_style_labels_shape():
    labels = style_labels()
    ids = {item["id"] for item in labels}
    assert ids == set(STYLE_LANGUAGES)
    for item in labels:
        assert item["label"] and "description" in item
        assert "emoji" in item and "accent" in item and "grayscale" in item
