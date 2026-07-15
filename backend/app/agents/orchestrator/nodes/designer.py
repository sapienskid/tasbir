"""Designer agent — generates HTML per format.

Input:  copy_by_format, background_by_format, design_tokens
Output: html_by_format (dict of format → full HTML document)
"""

from app.agents.orchestrator.state import GenerationState
from app.services.llm import call_llm
from app.agents.prompts.registry import get_prompt


async def designer_node(state: GenerationState) -> dict:
    prompt = await get_prompt("designer")
    html_by_format: dict[str, str] = {}

    for fmt in state["requested_formats"]:
        copy_text = state["copy_by_format"].get(fmt, "")
        bg = state["background_by_format"].get(fmt, {})
        tokens = state.get("design_tokens", {})

        user_prompt = (
            f"Format: {fmt}\n"
            f"Dimensions: {_get_format_dimensions(fmt)}\n"
            f"Copy: {copy_text}\n"
            f"Background CSS: {bg.get('css', '')}\n"
            f"Design tokens: {tokens}\n\n"
            f"Generate a complete HTML document for a social media post. "
            f"Use Tailwind CSS via CDN. Apply the background CSS. "
            f"Embed the copy text. No overflow, no scrollbars."
        )

        response = await call_llm(
            agent_role="designer",
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )

        html = _extract_html(response)
        html_by_format[fmt] = html

    return {"html_by_format": html_by_format, "next_node": "quality_check"}


def _get_format_dimensions(fmt: str) -> str:
    dims = {
        "instagram-square": "1080x1080",
        "instagram-portrait": "1080x1350",
        "instagram-story": "1080x1920",
        "twitter-card": "1200x628",
        "linkedin-post": "1200x627",
        "facebook-post": "1200x630",
        "pinterest-pin": "1000x1500",
        "carousel-post": "1080x1350",
    }
    return dims.get(fmt, "1080x1080")


def _extract_html(text: str) -> str:
    """Extract HTML from model response, stripping markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
