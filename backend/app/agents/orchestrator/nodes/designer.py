"""Designer node — creates HTML layouts per platform.

Uses YAML prompts from config/prompts/designer.yaml.
Will be rewritten in Phase 4.
"""

from app.agents.orchestrator.state import GenerationState


async def designer_node_single(state: GenerationState) -> dict:
    # TODO: Phase 4 — implement with YAML prompt + template system + CSS variable output
    return {"format_tasks": {}}
