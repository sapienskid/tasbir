"""Background generation service — zero cost CSS gradients + SVG patterns.

No API calls needed. All backgrounds are generated server-side as CSS code.
The AI agent chooses from presets based on content type and mood while strictly
following the user's brand guidelines (primary and secondary colors).
"""

import random
from dataclasses import dataclass


@dataclass
class BackgroundStyle:
    css: str
    name: str
    description: str


# Preset template gradients using dynamic brand color placeholders ({primary}, {secondary})
GRADIENT_PRESETS: dict[str, str] = {
    "sunset": "linear-gradient(135deg, {primary} 0%, {secondary} 100%)",
    "ocean": "linear-gradient(135deg, {primary} 0%, {secondary} 50%, #0f172a 100%)",
    "forest": "linear-gradient(135deg, {primary} 0%, {secondary} 100%)",
    "fire": "linear-gradient(135deg, {primary} 0%, {secondary} 100%)",
    "corporate": "linear-gradient(135deg, {primary} 0%, {secondary} 50%, #0f172a 100%)",
    "warm": "linear-gradient(135deg, {primary} 0%, {secondary} 100%)",
    "calm": "linear-gradient(135deg, {primary} 0%, {secondary} 100%)",
    "midnight": "linear-gradient(135deg, #090d16 0%, {primary}40 50%, {secondary}30 100%)",
    "minimal": "linear-gradient(135deg, #f8fafc 0%, {primary}10 50%, #f1f5f9 100%)",
    "gold": "linear-gradient(135deg, {primary} 0%, {secondary} 100%)",
    "aurora": "radial-gradient(at 0% 0%, {primary}60 0px, transparent 50%), radial-gradient(at 100% 100%, {secondary}50 0px, transparent 50%), #0d0f18",
    "modern-mesh": "radial-gradient(at 15% 15%, {primary}50 0px, transparent 50%), radial-gradient(at 85% 85%, {secondary}40 0px, transparent 50%), #0f172a",
    "obsidian-gold": "radial-gradient(circle at 75% 25%, {secondary}30 0%, transparent 55%), linear-gradient(135deg, #09090b 0%, {primary}40 100%)",
}

PATTERN_PRESETS: dict[str, str] = {
    "dots": "radial-gradient(circle, {color}18 1.2px, transparent 1.2px)",
    "grid": "linear-gradient({color}12 1px, transparent 1px), linear-gradient(90deg, {color}12 1px, transparent 1px)",
    "stripes": "repeating-linear-gradient(45deg, transparent, transparent 12px, {color}0f 12px, {color}0f 24px)",
    "crosshatch": "repeating-linear-gradient(0deg, transparent, transparent 12px, {color}0a 12px, {color}0a 13px), repeating-linear-gradient(90deg, transparent, transparent 12px, {color}0a 12px, {color}0a 13px)",
}


def generate_background(
    content_type: str,
    mood: str,
    brand_primary: str = "#667eea",
    brand_secondary: str = "#764ba2",
) -> BackgroundStyle:
    """Generate a background CSS strictly following brand guidelines (primary + secondary colors).

    Args:
        content_type: Type of content (article, quote, list, tutorial, story)
        mood: Desired mood (energetic, professional, calm, warm, minimal, luxury, cyber)
        brand_primary: Primary brand color (hex)
        brand_secondary: Secondary brand color (hex)

    Returns:
        BackgroundStyle with CSS and metadata.
    """
    primary = brand_primary or "#667eea"
    secondary = brand_secondary or "#764ba2"

    if content_type == "quote":
        return _generate_quote_background(primary, secondary)
    elif mood == "energetic" or mood == "cyber":
        return _generate_energetic_background(primary, secondary)
    elif content_type == "tutorial" or content_type == "list":
        return _generate_pattern_background(primary)
    elif content_type == "story" or mood == "luxury":
        return _generate_mesh_background(primary, secondary)
    else:
        return _generate_gradient_background(mood, primary, secondary)


def _generate_quote_background(primary: str, secondary: str = "") -> BackgroundStyle:
    sec = secondary if secondary else f"{primary}dd"
    return BackgroundStyle(
        css=f"background: linear-gradient(135deg, {primary} 0%, {sec} 100%);",
        name="solid-brand",
        description="Brand gradient quote background following brand guidelines",
    )


def _generate_energetic_background(primary: str, secondary: str) -> BackgroundStyle:
    angle = random.choice([135, 120, 150, 45])
    return BackgroundStyle(
        css=f"background: radial-gradient(circle at 20% 20%, {primary}40 0%, transparent 50%), linear-gradient({angle}deg, {primary} 0%, {secondary} 100%);",
        name="diagonal-brand-gradient",
        description="Energetic brand gradient with radial spotlight glow",
    )


def _generate_pattern_background(color: str) -> BackgroundStyle:
    pattern_type = random.choice(list(PATTERN_PRESETS.keys()))
    pattern_css = PATTERN_PRESETS[pattern_type].replace("{color}", color)
    size = random.choice([20, 30, 40])
    return BackgroundStyle(
        css=f"background-color: {color}; background-image: {pattern_css}; background-size: {size}px {size}px;",
        name=f"pattern-{pattern_type}",
        description=f"{pattern_type} pattern background with primary brand color",
    )


def _generate_mesh_background(primary: str, secondary: str) -> BackgroundStyle:
    return BackgroundStyle(
        css=(
            f"background: "
            f"radial-gradient(ellipse at 80% 20%, {primary}40 0%, transparent 60%), "
            f"radial-gradient(ellipse at 20% 80%, {secondary}30 0%, transparent 60%), "
            f"linear-gradient(135deg, #090d16 0%, #172033 100%);"
        ),
        name="brand-mesh-gradient",
        description="Dark mode mesh gradient dynamically blending brand primary and secondary colors",
    )


def _generate_gradient_background(mood: str, primary: str, secondary: str) -> BackgroundStyle:
    preset_name = mood if mood in GRADIENT_PRESETS else random.choice(list(GRADIENT_PRESETS.keys()))
    preset_template = GRADIENT_PRESETS.get(preset_name, GRADIENT_PRESETS["sunset"])
    css = preset_template.replace("{primary}", primary).replace("{secondary}", secondary)
    return BackgroundStyle(
        css=f"background: {css};",
        name=f"gradient-{preset_name}",
        description=f"{preset_name} gradient styled with user brand guidelines",
    )
