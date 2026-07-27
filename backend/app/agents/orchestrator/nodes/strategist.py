"""Strategist node — analyzes content and produces structured brief.

Uses YAML prompts from config/prompts/strategist.yaml.
Will be rewritten in Phase 4.
"""

from app.agents.orchestrator.state import GenerationState


async def strategist_node(state: GenerationState) -> dict:
    # TODO: Phase 4 — implement with YAML prompt + Pydantic output
    return {"strategic_brief": {}}
