"""Strategist agent (Aura Vance) — analyzes content and formulates campaign strategy.

Input:  title, content, tags, brand, campaign, requested_formats
Output: strategic_brief (stored in state)
"""

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import get_prompt
from app.services.llm import call_llm


async def strategist_node(state: GenerationState) -> dict:
    prompt = await get_prompt("strategist")

    user_prompt = (
        f"TITLE: {state['title']}\n\n"
        f"CONTENT:\n{state['content'][:5000]}\n\n"
        f"EXCERPT: {state.get('excerpt', '')}\n"
        f"TAGS: {', '.join(state.get('tags', []))}\n"
        f"BRAND CONTEXT: {state.get('brand', {})}\n"
        f"CAMPAIGN GOALS: {state.get('campaign', {})}\n"
        f"TARGET FORMATS: {', '.join(state['requested_formats'])}\n\n"
        f"As Aura Vance, analyze this content and synthesize a master Strategic Brief for our creative studio."
    )

    response = await call_llm(
        agent_role="strategist",
        system_prompt=prompt.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )

    return {"strategic_brief": response}
