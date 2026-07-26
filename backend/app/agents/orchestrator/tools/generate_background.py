"""Tool: Generate zero-cost CSS backgrounds."""

from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

from app.services.backgrounds import generate_background


async def generate_background_tool(
    state: Annotated[dict, InjectedState],
    style: str = "gradient",
    mood: str = "professional",
    brand_color: str = "",
) -> str:
    """Generate a CSS background style strictly following user brand guidelines.

    Zero-cost backgrounds: CSS gradients, SVG patterns, or solid colors.
    No external API calls needed.

    Args:
        style: 'gradient', 'pattern', 'solid', or 'unsplash'.
        mood: 'professional', 'energetic', 'calm', 'luxury', 'playful'.
        brand_color: Optional explicit hex color override.

    Returns:
        CSS background rule and a description of the generated style.
    """
    brand = state.get("brand", {})
    tokens = state.get("design_tokens", {})

    primary = (
        brand_color
        or brand.get("primary_color")
        or tokens.get("color", {}).get("primary", {}).get("$value")
        or "#667eea"
    )
    secondary = (
        brand.get("secondary_color")
        or tokens.get("color", {}).get("secondary", {}).get("$value")
        or "#764ba2"
    )

    bg = generate_background(content_type=style, mood=mood, brand_primary=primary, brand_secondary=secondary)
    return (
        f"Background: {bg.name}\n"
        f"CSS: {bg.css}\n"
        f"Description: {bg.description}"
    )
