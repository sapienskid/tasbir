"""Tool: Generate spacing scale for a design system."""
from langchain_core.tools import tool
import json


@tool
async def generate_spacing_tool(unit: str = "rem", scale: str = "t-shirt") -> str:
    """Generate a spacing scale for a design system.

    Returns DTCG-formatted spacing tokens.

    Args:
        unit: 'rem' or 'px'
        scale: 't-shirt' (2-4-6-8-12-16) or 'modular' (4-8-16-32-64)

    Returns:
        Spacing tokens in DTCG JSON format.
    """
    if scale == "modular":
        data = {
            "0": {"$value": "0", "$type": "dimension"},
            "1": {"$value": f"4{unit}" if unit == "px" else "0.25rem", "$type": "dimension"},
            "2": {"$value": f"8{unit}" if unit == "px" else "0.5rem", "$type": "dimension"},
            "3": {"$value": f"16{unit}" if unit == "px" else "1rem", "$type": "dimension"},
            "4": {"$value": f"32{unit}" if unit == "px" else "2rem", "$type": "dimension"},
            "5": {"$value": f"64{unit}" if unit == "px" else "4rem", "$type": "dimension"},
        }
    else:
        data = {
            "0": {"$value": "0", "$type": "dimension"},
            "2": {"$value": f"8{unit}" if unit == "px" else "0.5rem", "$type": "dimension"},
            "4": {"$value": f"16{unit}" if unit == "px" else "1rem", "$type": "dimension"},
            "6": {"$value": f"24{unit}" if unit == "px" else "1.5rem", "$type": "dimension"},
            "8": {"$value": f"32{unit}" if unit == "px" else "2rem", "$type": "dimension"},
            "12": {"$value": f"48{unit}" if unit == "px" else "3rem", "$type": "dimension"},
            "16": {"$value": f"64{unit}" if unit == "px" else "4rem", "$type": "dimension"},
        }
    return f"Spacing tokens (DTCG):\n```json\n{json.dumps(data, indent=2)}\n```"
