"""Tool: Generate accessible color palette for a design system."""
from langchain_core.tools import tool
import json

from app.services.color_tools import check_contrast, _lighten, _darken


@tool
async def generate_colors_tool(
    primary: str,
    secondary: str,
    accent: str = "#6366F1",
    mode: str = "dark",
) -> str:
    """Generate a complete accessible color palette for a design system.

    Returns DTCG-formatted color tokens with validated WCAG contrast.
    The palette works as a full-spectrum system with brand, neutral,
    semantic, and surface colors.

    Args:
        primary: Primary brand hex color (e.g. '#CD5B7D')
        secondary: Secondary brand hex color (e.g. '#5B7D7C')
        accent: Accent hex color (default '#6366F1')
        mode: 'dark' for dark backgrounds, 'light' for light backgrounds

    Returns:
        Complete color token set in DTCG JSON format with contrast report.
    """
    if mode == "light":
        bg = "#FFFFFF"
        surface = "#F3F4F6"
        elevated = "#E5E7EB"
        border = "#D1D5DB"
        text_primary = "#111827"
        text_secondary = "#6B7280"
        action_text = "#FFFFFF"
    else:
        bg = "#0A0A0C"
        surface = "#141418"
        elevated = "#202026"
        border = "#2C2C30"
        text_primary = "#EEE9E4"
        text_secondary = "#9B9BA0"
        action_text = "#FFFFFF"

    # Build the color structure
    data = {
        "color": {
            "brand": {
                "primary": {"main": {"$value": primary, "$type": "color"}},
                "secondary": {"main": {"$value": secondary, "$type": "color"}},
            },
            "neutral": {
                "white": {"$value": "#FFFFFF", "$type": "color"},
                "black": {"$value": "#000000", "$type": "color"},
                "bg": {"$value": bg, "$type": "color"},
                "surface": {"$value": surface, "$type": "color"},
                "elevated": {"$value": elevated, "$type": "color"},
                "border": {"$value": border, "$type": "color"},
            },
            "semantic": {
                "text": {
                    "primary": {"$value": text_primary, "$type": "color"},
                    "secondary": {"$value": text_secondary, "$type": "color"},
                    "inverse": {"$value": bg if mode == "light" else "#0A0A0C", "$type": "color"},
                    "link": {"$value": primary, "$type": "color"},
                },
                "background": {
                    "primary": {"$value": primary, "$type": "color"},
                    "secondary": {"$value": secondary, "$type": "color"},
                    "surface": {"$value": surface, "$type": "color"},
                    "elevated": {"$value": elevated, "$type": "color"},
                },
                "action": {
                    "primary": {"$value": primary, "$type": "color"},
                    "hover": {"$value": _lighten(primary, 15), "$type": "color"},
                    "muted": {"$value": _darken(primary, 20), "$type": "color"},
                    "text": {"$value": action_text, "$type": "color"},
                },
                "border": {
                    "default": {"$value": border, "$type": "color"},
                    "focus": {"$value": primary, "$type": "color"},
                },
            },
            "accent": {
                "default": {"$value": accent, "$type": "color"},
            },
        },
    }

    # Validate contrast
    pairs = [
        ("text.primary on bg", text_primary, bg),
        ("text.primary on surface", text_primary, surface),
        ("text.primary on brand", text_primary, primary),
        ("text.secondary on bg", text_secondary, bg),
        ("action.text on action", action_text, primary),
    ]
    report = []
    for label, fg, bg_c in pairs:
        c = check_contrast(fg, bg_c)
        status = "✓" if c["pass_normal"] else "✗"
        report.append(f"  {status} {label}: {c['ratio']}:1")

    contrast_report = "\n".join(report)
    return (
        f"Color tokens (DTCG):\n```json\n{json.dumps(data, indent=2)}\n```\n\n"
        f"Contrast validation:\n{contrast_report}"
    )
