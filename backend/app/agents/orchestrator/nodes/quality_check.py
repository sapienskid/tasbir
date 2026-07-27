"""Quality check / Verifier node — validates rendered images.

Uses YAML prompts from config/prompts/verifier.yaml.
Will be rewritten in Phase 4 with multimodal Gemini Vision.
"""

from app.agents.orchestrator.state import GenerationState


async def quality_check_node_single(state: GenerationState) -> dict:
    # TODO: Phase 4 — implement multimodal Verifier with Gemini Vision
    return {"format_tasks": {}}
