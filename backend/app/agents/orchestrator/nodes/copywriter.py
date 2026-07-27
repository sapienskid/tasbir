"""Copywriter node — produces structured copy per platform.

Uses YAML prompts from config/prompts/copywriter.yaml.
Will be rewritten in Phase 4.
"""

import asyncio
from app.agents.orchestrator.state import GenerationState


async def copywriter_node(state: GenerationState) -> dict:
    # TODO: Phase 4 — implement with YAML prompt + Pydantic output + Send fan-out
    return {"format_tasks": {}}
