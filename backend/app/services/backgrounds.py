"""Background generation service — zero cost CSS gradients + SVG patterns.

No API calls needed. All backgrounds are generated server-side as CSS code.
The AI agent chooses from presets based on content type and mood.
"""

import random
from dataclasses import dataclass


@dataclass
class BackgroundStyle:
    css: str
    name: str
    description: str


GRADIENT_PRESETS: dict[str, str] = {
    "sunset": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "ocean": "linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)",
    "forest": "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)",
    "fire": "linear-gradient(135deg, #f12711 0%, #f5af19 100%)",
    "corporate": "linear-gradient(135deg, #2c3e50 0%, #3498db 100%)",
    "warm": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    "calm": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    "midnight": "linear-gradient(135deg, #0f0c29 0%, #302b63 100%)",
    "minimal": "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
    "gold": "linear-gradient(135deg, #f5af19 0%, #f12711 100%)",
}

PATTERN_PRESETS: dict[str, str] = {
    "dots": "radial-gradient(circle, {color}15 1px, transparent 1px)",
    "grid": "linear-gradient({color}15 1px, transparent 1px), linear-gradient(90deg, {color}15 1px, transparent 1px)",
    "stripes": "repeating-linear-gradient(45deg, transparent, transparent 10px, {color}10 10px, {color}10 20px)",
    "crosshatch": "repeating-linear-gradient(0deg, transparent, transparent 10px, {color}08 10px, {color}08 11px), repeating-linear-gradient(90deg, transparent, transparent 10px, {color}08 10px, {color}08 11px)",
}


def generate_background(
    content_type: str,
    mood: str,
    brand_primary: str = "#667eea",
    brand_secondary: str = "#764ba2",
) -> BackgroundStyle:
    """Generate a background CSS based on content type and mood.

    This is entirely free — no API calls. The AI agent calls this
    function to choose the best background for each post format.

    Args:
        content_type: Type of content (article, quote, list, tutorial, story)
        mood: Desired mood (energetic, professional, calm, warm, minimal)
        brand_primary: Primary brand color (hex)
        brand_secondary: Secondary brand color (hex)

    Returns:
        BackgroundStyle with CSS and metadata.
    """
    if content_type == "quote":
        return _generate_quote_background(brand_primary)
    elif mood == "energetic":
        return _generate_energetic_background(brand_primary, brand_secondary)
    elif content_type == "tutorial" or content_type == "list":
        return _generate_pattern_background(brand_primary)
    elif content_type == "story":
        return _generate_mesh_background(brand_primary, brand_secondary)
    else:
        return _generate_gradient_background(mood, brand_primary, brand_secondary)


def _generate_quote_background(primary: str) -> BackgroundStyle:
    return BackgroundStyle(
        css=f"background: linear-gradient(135deg, {primary} 0%, {primary}dd 100%);",
        name="solid-brand",
        description="Solid brand color — minimal, text-focused",
    )


def _generate_energetic_background(primary: str, secondary: str) -> BackgroundStyle:
    angle = random.choice([135, 120, 150, 45])
    return BackgroundStyle(
        css=f"background: linear-gradient({angle}deg, {primary} 0%, {secondary} 100%);",
        name="diagonal-gradient",
        description="Diagonal gradient — energetic, modern",
    )


def _generate_pattern_background(color: str) -> BackgroundStyle:
    pattern_type = random.choice(list(PATTERN_PRESETS.keys()))
    pattern_css = PATTERN_PRESETS[pattern_type].replace("{color}", color)
    size = random.choice([20, 30, 40])
    return BackgroundStyle(
        css=f"background-color: {color}; background-image: {pattern_css}; background-size: {size}px {size}px;",
        name=f"pattern-{pattern_type}",
        description=f"{pattern_type} pattern background",
    )


def _generate_mesh_background(primary: str, secondary: str) -> BackgroundStyle:
    return BackgroundStyle(
        css=(
            f"background: "
            f"radial-gradient(ellipse at 80% 20%, {primary}30 0%, transparent 50%), "
            f"radial-gradient(ellipse at 20% 80%, {secondary}20 0%, transparent 50%), "
            f"radial-gradient(ellipse at 50% 50%, white 100%);"
        ),
        name="mesh-gradient",
        description="Mesh gradient — organic, modern",
    )


def _generate_gradient_background(mood: str, primary: str, secondary: str) -> BackgroundStyle:
    preset_name = mood if mood in GRADIENT_PRESETS else random.choice(list(GRADIENT_PRESETS.keys()))
    preset_css = GRADIENT_PRESETS[preset_name]
    # Substitute brand colors
    css = preset_css.replace("#667eea", primary).replace("#764ba2", secondary)
    return BackgroundStyle(
        css=f"background: {css};",
        name=f"gradient-{preset_name}",
        description=f"{preset_name} gradient background",
    )
