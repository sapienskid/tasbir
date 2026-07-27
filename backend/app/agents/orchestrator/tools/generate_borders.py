"""Tool: Generate border radius and shadow tokens for a design system."""
from langchain_core.tools import tool
import json


@tool
async def generate_borders_tool(style: str = "rounded") -> str:
    """Generate border radius and box shadow tokens for a design system.

    Args:
        style: 'rounded', 'sharp', 'mixed', 'pill'

    Returns:
        Border radius + box shadow tokens in DTCG JSON format.
    """
    if style == "sharp":
        radii = {
            "none": {"$value": "0", "$type": "dimension"},
            "sm": {"$value": "1px", "$type": "dimension"},
            "md": {"$value": "2px", "$type": "dimension"},
            "lg": {"$value": "4px", "$type": "dimension"},
        }
    elif style == "pill":
        radii = {
            "none": {"$value": "0", "$type": "dimension"},
            "sm": {"$value": "0.25rem", "$type": "dimension"},
            "md": {"$value": "0.5rem", "$type": "dimension"},
            "lg": {"$value": "1rem", "$type": "dimension"},
            "xl": {"$value": "1.5rem", "$type": "dimension"},
            "full": {"$value": "9999px", "$type": "dimension"},
        }
    else:
        radii = {
            "none": {"$value": "0", "$type": "dimension"},
            "sm": {"$value": "0.125rem", "$type": "dimension"},
            "md": {"$value": "0.375rem", "$type": "dimension"},
            "lg": {"$value": "0.5rem", "$type": "dimension"},
            "xl": {"$value": "0.75rem", "$type": "dimension"},
            "2xl": {"$value": "1rem", "$type": "dimension"},
            "full": {"$value": "9999px", "$type": "dimension"},
        }

    shadows = {
        "sm": {"$value": "0 1px 2px 0 rgba(0,0,0,0.05)", "$type": "shadow"},
        "md": {"$value": "0 4px 6px -1px rgba(0,0,0,0.1)", "$type": "shadow"},
        "lg": {"$value": "0 10px 15px -3px rgba(0,0,0,0.1)", "$type": "shadow"},
        "xl": {"$value": "0 20px 25px -5px rgba(0,0,0,0.25)", "$type": "shadow"},
    }

    data = {"borderRadius": radii, "boxShadow": shadows}
    return f"Border & shadow tokens (DTCG):\n```json\n{json.dumps(data, indent=2)}\n```"
