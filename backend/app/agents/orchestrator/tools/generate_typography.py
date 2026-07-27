"""Tool: Generate typography scale for a design system."""
from langchain_core.tools import tool


@tool
async def generate_typography_tool(
    style: str = "modern",
    heading_font: str = "",
    body_font: str = "",
) -> str:
    """Generate a complete typography scale for a design system.

    Returns DTCG-formatted typography tokens including font families,
    font sizes, font weights, line heights, and letter spacing.

    Args:
        style: 'modern', 'classic', 'minimal', 'editorial', 'tech'
        heading_font: Preferred heading font (e.g., 'Instrument Serif')
        body_font: Preferred body font (e.g., 'Inter')

    Returns:
        Complete typography token set in DTCG JSON format.
    """
    sans = body_font or "Inter, system-ui, sans-serif"
    serif = heading_font or "Instrument Serif, Georgia, serif"
    display = heading_font or "Instrument Serif, serif"

    if style == "editorial":
        sans = body_font or "Merriweather, Georgia, serif"
        serif = heading_font or "Playfair Display, Georgia, serif"
        display = heading_font or "Playfair Display, serif"
    elif style == "tech":
        sans = body_font or "Inter, system-ui, sans-serif"
        serif = heading_font or "DM Serif Display, serif"
        display = heading_font or "DM Serif Display, serif"
    elif style == "minimal":
        sans = body_font or "Inter, system-ui, sans-serif"
        serif = heading_font or "Inter, system-ui, sans-serif"
        display = heading_font or "Inter, system-ui, sans-serif"

    import json
    data = {
        "fontFamily": {
            "sans": {"$value": sans, "$type": "fontFamily"},
            "serif": {"$value": serif, "$type": "fontFamily"},
            "mono": {"$value": "JetBrains Mono, monospace", "$type": "fontFamily"},
        },
        "fontSize": {
            "xs": {"$value": "0.75rem", "$type": "dimension"},
            "sm": {"$value": "0.875rem", "$type": "dimension"},
            "base": {"$value": "1rem", "$type": "dimension"},
            "lg": {"$value": "1.125rem", "$type": "dimension"},
            "xl": {"$value": "1.25rem", "$type": "dimension"},
            "2xl": {"$value": "1.5rem", "$type": "dimension"},
            "3xl": {"$value": "1.875rem", "$type": "dimension"},
            "4xl": {"$value": "2.25rem", "$type": "dimension"},
        },
        "fontWeight": {
            "light": {"$value": "300", "$type": "number"},
            "normal": {"$value": "400", "$type": "number"},
            "medium": {"$value": "500", "$type": "number"},
            "semibold": {"$value": "600", "$type": "number"},
            "bold": {"$value": "700", "$type": "number"},
        },
        "lineHeight": {
            "tight": {"$value": "1.15", "$type": "number"},
            "snug": {"$value": "1.35", "$type": "number"},
            "normal": {"$value": "1.5", "$type": "number"},
            "relaxed": {"$value": "1.625", "$type": "number"},
        },
        "letterSpacing": {
            "tight": {"$value": "-0.025em", "$type": "dimension"},
            "normal": {"$value": "0", "$type": "dimension"},
            "wide": {"$value": "0.025em", "$type": "dimension"},
            "wider": {"$value": "0.05em", "$type": "dimension"},
            "widest": {"$value": "0.1em", "$type": "dimension"},
        },
    }
    return f"Typography tokens (DTCG):\n```json\n{json.dumps(data, indent=2)}\n```"
