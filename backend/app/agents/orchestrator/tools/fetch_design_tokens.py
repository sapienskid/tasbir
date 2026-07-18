"""Tool: Fetch design tokens for a brand."""

from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated


async def fetch_design_tokens(
    state: Annotated[dict, InjectedState],
    brand_name: str = "",
) -> str:
    """Fetch design tokens (colors, fonts, spacing) for a brand.

    Design tokens are stored in DTCG format and synchronized with Penpot.
    Use these tokens to ensure brand consistency in generated designs.

    Args:
        brand_name: Optional brand name to filter tokens.

    Returns:
        Design token data formatted for use in HTML/Tailwind generation.
    """
    tokens = state.get("design_tokens", {})

    if not tokens:
        return "No design tokens configured. Use default Tailwind classes."

    if brand_name and brand_name in tokens:
        tokens = {brand_name: tokens[brand_name]}

    flat = {}
    for group, group_data in tokens.items():
        if isinstance(group_data, dict):
            for category, values in group_data.items():
                if isinstance(values, dict):
                    for name, token in values.items():
                        if isinstance(token, dict) and "$value" in token:
                            flat[f"{group}/{category}/{name}"] = token["$value"]

    if not flat:
        return "No design tokens found."

    lines = [f"  {path}: {value}" for path, value in sorted(flat.items())]
    return "Design Tokens:\n" + "\n".join(lines)
