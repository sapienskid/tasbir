"""Copywriter agent (Julian Sterling) — generates per-format copy in parallel using dynamic DB formats.

Input:  strategic_brief, requested_formats, content
Output: copy_by_format (dict of format → copy text)
"""

import asyncio
from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import PromptVersion, get_prompt
from app.services.formats import get_format_info
from app.services.llm import call_llm


async def _generate_copy_for_format(
    fmt_id: str,
    state: GenerationState,
    prompt: PromptVersion,
) -> tuple[str, str]:
    fmt_info = await get_format_info(fmt_id)
    fmt_narrative = f"\nFormat narrative: {fmt_info.ai_instruction}" if fmt_info.ai_instruction else ""

    user_prompt = (
        f"FORMAT: {fmt_info.name} ({fmt_info.id})\n"
        f"TARGET DIMENSIONS: {fmt_info.width}x{fmt_info.height}\n"
        f"{fmt_narrative}\n\n"
        f"TITLE: {state['title']}\n"
        f"SOURCE CONTENT SUMMARY:\n{state['content'][:2000]}\n\n"
        f"STRATEGIC BRIEF:\n{state.get('strategic_brief', '')}\n\n"
        f"As Julian Sterling, craft visually optimized, layout-ready copy for this canvas format. "
        f"STRICT CONSTRAINT: Do NOT use any emojis under any circumstances."
    )

    response = await call_llm(
        agent_role="copywriter",
        system_prompt=prompt.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    return fmt_id, response


async def copywriter_node(state: GenerationState) -> dict:
    prompt = await get_prompt("copywriter")
    formats = state["requested_formats"]

    tasks = [_generate_copy_for_format(fmt, state, prompt) for fmt in formats]
    results = await asyncio.gather(*tasks)

    copy_by_format = {fmt: copy for fmt, copy in results}
    return {"copy_by_format": copy_by_format, "next_node": "designer"}
