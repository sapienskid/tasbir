"""Renderer node — converts HTML to PNG via Playwright.

Will be replaced by HTML→Penpot converter in Phase 4.
"""

from app.agents.orchestrator.state import GenerationState


async def renderer_node_single(state: GenerationState) -> dict:
    # TODO: Phase 4 — implement HTML→Penpot + SVG→PNG pipeline
    return {"format_tasks": {}}
