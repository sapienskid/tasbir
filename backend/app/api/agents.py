"""Agents API — CRUD for DB-backed agent configs + pipeline graph topology."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.agents import AgentRepository
from app.services import agents as agent_service

log = logging.getLogger(__name__)

router = APIRouter()


class AgentUpdate(BaseModel):
    persona: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=65536)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Graph topology for the Studio React Flow page.
#
# Topology lives in code (agents are typed Python nodes) — this is a static
# *description* of the graph, enriched with live config at request time so
# the page shows real persona/model/state per node.
# ---------------------------------------------------------------------------
GRAPH_SPEC: dict = {
    "nodes": [
        {"id": "start", "label": "Start", "kind": "start"},
        {"id": "strategist", "label": "Strategist", "kind": "agent", "agent": "strategist"},
        {"id": "copywriter", "label": "Copywriter", "kind": "agent", "agent": "copywriter"},
        {"id": "process_all_formats", "label": "Process All Formats", "kind": "group"},
        {"id": "end", "label": "End", "kind": "end"},
    ],
    "edges": [
        {"id": "e-start->strategist", "source": "start", "target": "strategist"},
        {"id": "e-strategist->copywriter", "source": "strategist", "target": "copywriter"},
        {"id": "e-copywriter->process", "source": "copywriter", "target": "process_all_formats"},
        {"id": "e-process->end", "source": "process_all_formats", "target": "end"},
    ],
    "subflow": {
        "id": "process_all_formats",
        "label": "Per-format chain (runs in parallel)",
        "nodes": [
            {"id": "template", "label": "Template", "kind": "pipeline"},
            {"id": "designer", "label": "Designer", "kind": "agent", "agent": "designer"},
            {"id": "renderer", "label": "Renderer", "kind": "pipeline"},
            {"id": "verifier", "label": "Verifier", "kind": "agent", "agent": "verifier"},
        ],
        "edges": [
            {"id": "se-template->designer", "source": "template", "target": "designer"},
            {"id": "se-designer->renderer", "source": "designer", "target": "renderer"},
            {"id": "se-renderer->verifier", "source": "renderer", "target": "verifier"},
            {
                "id": "se-verifier->designer",
                "source": "verifier",
                "target": "designer",
                "label": "retry",
            },
        ],
    },
    # Non-pipeline agent lanes — the brand builder, template author, and
    # editor-chat chains. Rendered as clickable lanes in the Studio.
    "aux_lanes": [
        {
            "id": "brand_builder",
            "label": "Brand Builder (design system from input)",
            "agents": ["brand_vision", "brand_tokens", "brand_campaigns"],
        },
        {
            "id": "template_author",
            "label": "Template Author (template from image)",
            "agents": ["template_vision", "template_author"],
        },
        {
            "id": "editor_chat",
            "label": "Editor Chat (task conversation)",
            "agents": ["editor_chat"],
        },
    ],
}


def _enrich_node(node: dict, config: dict) -> dict:
    """Fill persona/model/state from a live agent config (when present)."""
    if node.get("kind") == "agent":
        agent_name = node.get("agent", "")
        row = config.get(agent_name)
        node = dict(node)
        node["persona"] = (row or {}).get("persona", "")
        node["model"] = (row or {}).get("model", "")
        node["is_active"] = bool((row or {}).get("is_active", True))
    return node


@router.get("/graph")
async def agent_graph(db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    rows = await repo.list(include_inactive=True)
    config = {r.name: agent_service.agent_to_dict(r) for r in rows}
    spec = {
        "nodes": [_enrich_node(n, config) for n in GRAPH_SPEC["nodes"]],
        "edges": GRAPH_SPEC["edges"],
        "subflow": {
            **GRAPH_SPEC["subflow"],
            "nodes": [_enrich_node(n, config) for n in GRAPH_SPEC["subflow"]["nodes"]],
        },
        "aux_lanes": [
            {
                **lane,
                "agents": [
                    {
                        "name": name,
                        "persona": (config.get(name) or {}).get("persona", ""),
                        "model": (config.get(name) or {}).get("model", ""),
                        "is_active": bool((config.get(name) or {}).get("is_active", True)),
                    }
                    for name in lane["agents"]
                ],
            }
            for lane in GRAPH_SPEC.get("aux_lanes", [])
        ],
    }
    return spec


@router.get("")
async def list_agents(
    include_inactive: bool = False, db: AsyncSession = Depends(get_db)
):
    repo = AgentRepository(db)
    rows = await repo.list(include_inactive=include_inactive)
    return [agent_service.agent_to_dict(r) for r in rows]


@router.get("/{name}")
async def get_agent(name: str, db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    row = await repo.get_by_name(name)
    if row is None:
        raise NotFoundError(f"Agent {name} not found")
    return agent_service.agent_to_dict(row)


@router.put("/{name}")
async def update_agent(name: str, body: AgentUpdate, db: AsyncSession = Depends(get_db)):
    repo = AgentRepository(db)
    if await repo.get_by_name(name) is None:
        raise NotFoundError(f"Agent {name} not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("system_prompt") is not None and not data["system_prompt"].strip():
        raise HTTPException(status_code=422, detail="system_prompt cannot be empty")
    await repo.update(name, data)
    agent_service.invalidate_agent_config(name)
    row = await repo.get_by_name(name)
    return agent_service.agent_to_dict(row)


@router.post("/{name}/reset")
async def reset_agent(name: str, db: AsyncSession = Depends(get_db)):
    row = await agent_service.reset_agent(db, name)
    if row is None:
        raise NotFoundError(f"Agent {name} not found")
    return agent_service.agent_to_dict(row)


class PromptPreviewRequest(BaseModel):
    design_system_id: str = "default"


@router.post("/{name}/prompt-preview")
async def prompt_preview(name: str, body: PromptPreviewRequest, db: AsyncSession = Depends(get_db)):
    """Assemble the system + user prompt for an agent (representative sample).

    User prompts are built dynamically by each node — this endpoint
    reconstructs what a real run would send, so the Studio can show it.
    """
    repo = AgentRepository(db)
    if await repo.get_by_name(name) is None:
        raise NotFoundError(f"Agent {name} not found")

    from app.services.prompt_preview import build_prompt_preview

    return await build_prompt_preview(name, body.design_system_id)
