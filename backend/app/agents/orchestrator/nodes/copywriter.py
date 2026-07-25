"""Copywriter agent — generates per-format copy.

Input:  strategic_brief, requested_formats, content
Output: copy_by_format (dict of format → copy text)
"""

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import get_prompt
from app.services.llm import call_llm
from app.db.session import create_pool
from app.config import get_settings
from sqlalchemy import select


async def _get_format_instruction(fmt_id: str) -> str:
    try:
        from app.models.format import Format
        s = get_settings()
        engine, pool = await create_pool(s.database_url)
        async with pool() as session:
            result = await session.execute(select(Format).where(Format.id == fmt_id))
            fmt = result.scalar_one_or_none()
            await engine.dispose()
            return fmt.ai_instruction if fmt and fmt.ai_instruction else ""
    except Exception:
        return ""


async def copywriter_node(state: GenerationState) -> dict:
    prompt = await get_prompt("copywriter")
    copy_by_format: dict[str, str] = {}

    for fmt in state["requested_formats"]:
        instruction = await _get_format_instruction(fmt)
        fmt_context = f"\nFormat narrative: {instruction}" if instruction else ""

        user_prompt = (
            f"Format: {fmt}\n"
            f"Dimensions: {_get_dims(fmt)}\n"
            f"{fmt_context}\n\n"
            f"Content: {state['title']}\n"
            f"{state['content'][:2000]}\n\n"
            f"Strategic brief: {state.get('strategic_brief', '')}\n\n"
            f"Write engaging copy optimized for this format."
        )

        response = await call_llm(
            agent_role="copywriter",
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        copy_by_format[fmt] = response

    return {"copy_by_format": copy_by_format, "next_node": "visual_director"}


def _get_dims(fmt: str) -> str:
    dims = {
        "instagram-square": "1080x1080",
        "instagram-portrait": "1080x1350",
        "instagram-story": "1080x1920",
        "twitter-card": "1200x675",
        "linkedin-post": "1200x627",
        "facebook-post": "1200x630",
        "pinterest-pin": "1000x1500",
        "carousel-post": "1080x1350",
    }
    return dims.get(fmt, "1080x1080")
