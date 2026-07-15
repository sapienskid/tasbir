"""Copywriter agent — generates per-format copy.

Input:  strategic_brief, requested_formats, content
Output: copy_by_format (dict of format → copy text)
"""

from app.agents.orchestrator.state import GenerationState
from app.services.llm import call_llm
from app.agents.prompts.registry import get_prompt


async def copywriter_node(state: GenerationState) -> dict:
    prompt = await get_prompt("copywriter")
    copy_by_format: dict[str, str] = {}

    for fmt in state["requested_formats"]:
        user_prompt = (
            f"Format: {fmt}\n\n"
            f"Content: {state['title']}\n"
            f"{state['content'][:2000]}\n\n"
            f"Strategic brief: {state.get('strategic_brief', '')}\n\n"
            f"Write engaging copy for this format."
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
