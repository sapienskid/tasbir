"""Tool: Fetch design tokens for a brand."""
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool
from typing_extensions import Annotated


@tool
async def fetch_design_tokens(
    brand_name: str = "",
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Fetch design tokens (colors, typography, radii, spacing, logo) for a brand.

    Design tokens are stored in DTCG format and synchronized with Penpot.
    Use these tokens to ensure brand consistency in generated designs.

    Args:
        brand_name: Optional brand name to filter tokens.

    Returns:
        Design token data formatted for use in HTML/Tailwind generation.
    """
    tokens = state.get("design_tokens", {})
    brand = state.get("brand", {})

    flat = {}
    if tokens:
        for group, group_data in tokens.items():
            if isinstance(group_data, dict):
                for category, values in group_data.items():
                    if isinstance(values, dict):
                        for name, token in values.items():
                            if isinstance(token, dict) and "$value" in token:
                                flat[f"{group}/{category}/{name}"] = token["$value"]
                            elif isinstance(token, (str, int, float)):
                                flat[f"{group}/{category}/{name}"] = str(token)

    lines = []
    if brand.get("name"):
        lines.append(f"Brand: {brand.get('name')}")
    if brand.get("primary_color"):
        lines.append(f"  Primary Color: {brand.get('primary_color')}")
    if brand.get("secondary_color"):
        lines.append(f"  Secondary Color: {brand.get('secondary_color')}")
    if brand.get("logo_url"):
        lines.append(f"  Brand Logo URL: {brand.get('logo_url')}")

    if flat:
        lines.append("Design Tokens (DTCG):")
        for path, value in sorted(flat.items()):
            lines.append(f"  {path}: {value}")

    if not lines:
        return "No explicit design tokens configured. Use standard brand colors and clean Tailwind styling."

    return "\n".join(lines)
