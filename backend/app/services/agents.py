"""Agent configuration service — DB-backed agent configs.

v3.5 moved agent personas/prompts/models into SQLite, mirroring the
design-system/template migration (ADR-0012). ``get_agent_config`` is the
single runtime entry point every node/service uses: **DB row → YAML seed →
hardcoded fallback**, with a short TTL cache so edits propagate without a
worker restart.

The YAML prompt files seed first boot only. From then on the Studio owns the
rows — there is deliberately **no boot reconcile** (unlike design systems),
so a YAML edit never clobbers a Studio edit. Restore a seed prompt via
``POST /api/agents/{name}/reset``.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.prompts.registry import PromptConfig
from app.agents.prompts.registry import load_prompt as load_prompt_yaml
from app.core.time import iso_utc
from app.db.repositories.agents import AgentRepository
from app.db.session import get_shared_session_factory
from app.models.agent import Agent
from app.services.llm import MODEL_ROUTES

log = logging.getLogger(__name__)

_CACHE_TTL = 5.0
_agent_cache: dict[str, tuple[float, PromptConfig]] = {}


def invalidate_agent_config(name: str | None = None) -> None:
    """Drop cached config(s). Call after a DB update so changes apply fast."""
    if name is None:
        _agent_cache.clear()
    else:
        _agent_cache.pop(name, None)


async def get_agent_config(name: str) -> PromptConfig:
    """Resolve an agent config: DB row → YAML seed → hardcoded fallback.

    TTL-cached (~5s) and invalidated on update so prompt/model edits apply
    without a worker restart. Never raises for a missing row or DB hiccup —
    it falls back to the YAML seed so the pipeline always runs.
    """
    now = time.monotonic()
    cached = _agent_cache.get(name)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    cfg: PromptConfig | None = None
    try:
        pool = await get_shared_session_factory()
        async with pool() as session:
            row = await AgentRepository(session).get_by_name(name)
        if row is not None and row.is_active:
            cfg = PromptConfig(
                persona=row.persona,
                role=row.role,
                system_prompt=row.system_prompt,
                model=row.model,
                temperature=row.temperature,
                max_tokens=row.max_tokens,
            )
    except Exception as e:  # noqa: BLE001
        log.warning("[agents] DB lookup failed for %r, falling back to YAML: %s", name, e)

    if cfg is None:
        cfg = load_prompt_yaml(name)
        if not cfg.model:
            cfg.model = MODEL_ROUTES.get(name, "")

    _agent_cache[name] = (now, cfg)
    return cfg


def resolve_model(agent_role: str) -> str:
    """DB model for a role, falling back to MODEL_ROUTES defaults.

    Sync: reads the warm cache (populated by get_agent_config in the same
    node flow) or falls back to MODEL_ROUTES. Kept sync so ``get_llm`` can
    stay synchronous.
    """
    cached = _agent_cache.get(agent_role)
    if cached is not None:
        model = cached[1].model
        if model:
            return model
    return MODEL_ROUTES.get(agent_role, "gemini-2.0-flash")


def agent_to_dict(agent: Agent) -> dict:
    """Serialize an agent row for API responses."""
    return {
        "name": agent.name,
        "persona": agent.persona,
        "role": agent.role,
        "system_prompt": agent.system_prompt,
        "model": agent.model,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "source": agent.source,
        "is_active": bool(agent.is_active),
        "created_at": iso_utc(agent.created_at),
        "updated_at": iso_utc(agent.updated_at),
    }


async def seed_agents(pool: async_sessionmaker[AsyncSession]) -> int:
    """Idempotently import the YAML prompt files + MODEL_ROUTES on first boot.

    Only creates missing rows — existing rows (even seed ones) are never
    touched here. Returns how many were created.
    """
    async with pool() as session:
        repo = AgentRepository(session)
        existing = await repo.list(include_inactive=True)
        existing_names = {a.name for a in existing}
        seeded = 0
        for name in MODEL_ROUTES:
            if name in existing_names:
                continue
            cfg = load_prompt_yaml(name)
            await repo.create(
                name,
                {
                    "persona": cfg.persona,
                    "role": cfg.role,
                    "system_prompt": cfg.system_prompt,
                    "model": cfg.model or MODEL_ROUTES.get(name, ""),
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "source": "seed",
                    "is_active": True,
                },
            )
            seeded += 1
        if seeded:
            log.info("[agents] Seeded %d agent config(s)", seeded)
    return seeded


async def reset_agent(session: AsyncSession, name: str) -> Agent | None:
    """Restore an agent row from the YAML seed content.

    Marks it ``source="seed"`` again. Returns the refreshed row.
    """
    cfg = load_prompt_yaml(name)
    repo = AgentRepository(session)
    agent = await repo.get_by_name(name)
    if agent is None:
        return None
    await repo.update(
        name,
        {
            "persona": cfg.persona,
            "role": cfg.role,
            "system_prompt": cfg.system_prompt,
            "model": cfg.model or MODEL_ROUTES.get(name, ""),
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "source": "seed",
        },
    )
    invalidate_agent_config(name)
    return await repo.get_by_name(name)
