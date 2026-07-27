"""Copywriter agent (Julian Sterling) — generates per-format copy in parallel using dynamic DB formats.

Input:  strategic_brief, requested_formats, content
Output: copy_by_format (dict of format → copy text)
"""

import asyncio
from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import PromptVersion, get_prompt
from app.services.formats import get_format_info
from app.services.llm import call_llm

# Required structured fields in every copywriter output
_REQUIRED_FIELDS = ["HEADLINE:", "SUBHEAD:", "KEY POINTS:", "BADGE:", "TAGLINE:"]


def _validate_copy_fields(copy_text: str) -> bool:
    """Validate that the LLM copy output contains all required structured fields."""
    return all(field in copy_text for field in _REQUIRED_FIELDS)


async def _generate_copy_for_format(
    fmt_id: str,
    state: GenerationState,
    prompt: PromptVersion,
) -> tuple[str, str]:
    fmt_info = await get_format_info(fmt_id)
    fmt_narrative = f"FORMAT INSTRUCTION: {fmt_info.ai_instruction}" if fmt_info.ai_instruction else ""
    brand = state.get("brand", {})
    user_badge = state.get("badge_tag") or state.get("badge")

    badge_instruction = (
        f"USER-SPECIFIED BADGE TAG: \"{user_badge}\" (use this exact text for BADGE)"
        if user_badge
        else "USER-SPECIFIED BADGE TAG: NONE (No badge requested by user — output BADGE: None)"
    )

    user_prompt = (
        f"FORMAT: {fmt_info.name} ({fmt_info.id})\n"
        f"TARGET DIMENSIONS: {fmt_info.width}x{fmt_info.height}\n"
        f"{fmt_narrative}\n\n"
        f"BRAND: {brand.get('name', '')} — Tone: {brand.get('tone', 'professional')}\n\n"
        f"TITLE: {state['title']}\n"
        f"SOURCE CONTENT (derive ALL copy STRICTLY from this — write like a human, NO AI clichés, NO fantasizing):\n{state['content'][:4000]}\n\n"
        f"STRATEGIC BRIEF:\n{state.get('strategic_brief', '')}\n\n"
        f"{badge_instruction}\n\n"
        f"Craft human-written, layout-ready copy for this format. "
        f"STRICT CONSTRAINTS: NO emojis. Write like a real human. If user badge tag is NONE, output BADGE: None.\n"
        f"Enforce character limits strictly — rewrite if needed: HEADLINE ≤50 chars, SUBHEAD ≤120 chars, KEY POINT ≤70 chars, TAGLINE ≤40 chars."
    )

    response = await call_llm(
        agent_role="copywriter",
        system_prompt=prompt.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )

    # Validate all required structured fields are present; retry once if missing
    if not _validate_copy_fields(response):
        reminder = (
            "Your previous response is missing required fields. "
            "You MUST output exactly these 5 fields and nothing else:\n"
            "HEADLINE: ...\nSUBHEAD: ...\nKEY POINTS: ...\nBADGE: ...\nTAGLINE: ..."
        )
        response = await call_llm(
            agent_role="copywriter",
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt + "\n\n" + reminder,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )

    return fmt_id, response


async def copywriter_node(state: GenerationState) -> dict:
    prompt = await get_prompt("copywriter")
    formats = state["requested_formats"]

    semaphore = asyncio.Semaphore(1)

    async def _with_semaphore(fmt: str):
        async with semaphore:
            return await _generate_copy_for_format(fmt, state, prompt)

    results = await asyncio.gather(*[_with_semaphore(f) for f in formats])

    copy_by_format = {fmt: copy for fmt, copy in results}
    return {"copy_by_format": copy_by_format}
