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
    """Generate a CSS background style for a social media post.

    Zero-cost backgrounds: CSS gradients, SVG patterns, or solid colors.
    No external API calls needed.

    Args:
        style: 'gradient', 'pattern', 'solid', or 'unsplash'.
        mood: 'professional', 'energetic', 'calm', 'luxury', 'playful'.
        brand_color: Hex color to use as base (e.g., '#0066cc').

    Returns:
        CSS background rule and a description of the generated style.
    """
    bg = generate_background(content_type=style, mood=mood)
    css = bg.css
    if brand_color:
        css = css.replace("#667eea", brand_color).replace("#764ba2", brand_color)

    return (
        f"Background: {bg.name}\n"
        f"CSS: {css}\n"
        f"Description: {bg.description}"
    )
