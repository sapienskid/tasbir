"""Strategist agent — analyzes content and plans campaign.

Input:  title, content, tags, brand, campaign, requested_formats
Output: strategic_brief (stored in state)
"""

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import get_prompt
from app.services.llm import call_llm


async def strategist_node(state: GenerationState) -> dict:
    prompt = await get_prompt("strategist")

    user_prompt = (
        f"Title: {state['title']}\n\n"
        f"Content: {state['content'][:5000]}\n\n"
        f"Tags: {', '.join(state['tags'])}\n\n"
        f"Brand: {state.get('brand', {})}\n"
        f"Campaign: {state.get('campaign', {})}\n\n"
        f"Requested formats: {', '.join(state['requested_formats'])}\n\n"
        f"Analyze this content and produce a strategic brief."
    )

    response = await call_llm(
        agent_role="strategist",
        system_prompt=prompt.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )

    return {"strategic_brief": response, "next_node": "copywriter"}
