"""Tool: Check WCAG color contrast between two hex colors."""
from langchain_core.tools import tool
from app.services.color_tools import check_contrast as _check


@tool
async def check_contrast_tool(foreground: str, background: str, level: str = "AA") -> str:
    """Check WCAG color contrast between two hex colors.

    Use this when generating or validating design tokens to ensure text
    is readable on its background. For a dark theme, text must be light
    and pass WCAG AA (4.5:1 for normal text, 3:1 for large text).

    Args:
        foreground: Foreground hex color (e.g. '#EEE9E4' or '#000000').
        background: Background hex color (e.g. '#141418' or '#CD5B7D').
        level: 'AA' (standard) or 'AAA' (enhanced).

    Returns:
        Contrast ratio and pass/fail status with recommendations.
    """
    result = _check(foreground, background, level)
    parts = [
        f"Contrast ratio: {result['ratio']}:1",
        f"Level: {result['level']}",
        f"Passes normal text: {'YES' if result['pass_normal'] else 'NO'}",
        f"Passes large text: {'YES' if result['pass_large'] else 'NO'}",
    ]
    if not result["pass_normal"]:
        ratio = result["ratio"]
        if ratio < 3.0:
            parts.append("RECOMMENDATION: Text is nearly invisible. Use a much lighter foreground or darker background.")
        elif ratio < 4.5:
            parts.append("RECOMMENDATION: Use this color only for large text (18px+ bold or 14px+ 24px). For body text, lighten the foreground.")
        else:
            parts.append("Meets WCAG AA requirements.")
    return "\n".join(parts)
