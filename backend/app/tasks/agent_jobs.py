"""Celery agent-jobs — template-from-image and design-system-from-input.

Each job updates its AgentJob row as it progresses so the UI can poll
GET /agent-jobs/{id}.
"""

from __future__ import annotations

import asyncio
import base64
import logging

from app.db.repositories.agent_jobs import AgentJobRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


async def _run_template_job(job_id: str, payload: dict) -> None:
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_systems import DEFAULT_ID
    from app.services.template_author import (
        author_template_html,
        build_layout_spec,
        validate_template_html,
    )
    from app.services.templates import scan_template_features

    pool = await get_shared_session_factory()

    async with pool() as session:
        await AgentJobRepository(session).update_status(job_id, "running")

    ds_id = payload.get("design_system_id") or DEFAULT_ID
    async with pool() as session:
        ds = await DesignSystemRepository(session).get_by_id(ds_id)
    if ds is None:
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "failed", error=f"Design system {ds_id!r} not found"
            )
        return

    image_bytes = base64.b64decode(payload.get("image", ""))
    mime = payload.get("mime") or "image/png"

    try:
        spec = await build_layout_spec(image_bytes, mime)
        family = (
            spec.get("family")
            if spec.get("family") in ("square", "portrait", "story", "landscape")
            else "square"
        )
        ground = spec.get("ground") if spec.get("ground") in ("white", "black") else "white"

        html = await author_template_html(spec, ds, ground_hint=ground)
        result = await validate_template_html(html, family, ds, ground)
        for _ in range(2):
            if result["ok"]:
                break
            html = await author_template_html(
                spec, ds, critique=result["critique"], ground_hint=ground
            )
            result = await validate_template_html(html, family, ds, ground)
        if not result["ok"]:
            async with pool() as session:
                await AgentJobRepository(session).update_status(
                    job_id, "failed",
                    error="Template failed validation: " + "; ".join(result["issues"][:5]),
                )
            return

        import re as _re

        slug = _re.sub(r"[^a-z0-9]+", "-", (spec.get("layout_description") or "ai").lower())
        slug = _re.sub(r"^-+|-+$", "", slug)[:32]
        template_id = f"{ds.id}-{slug or 'ai'}"
        image_slots, has_logo = scan_template_features(html)

        from app.db.repositories.templates import TemplateRepository

        async with pool() as session:
            tpl_repo = TemplateRepository(session)
            base = template_id
            n = 2
            while await tpl_repo.get_by_id(template_id):
                template_id = f"{base}-{n}"
                n += 1
            await tpl_repo.create(
                {
                    "id": template_id,
                    "design_system_id": ds.id,
                    "name": slug or "AI template",
                    "family": family,
                    "grounds": (
                        [ground]
                        if 'data-ground="black"' not in html
                        else ["white", "black"]
                    ),
                    "categories": ["WRITING"],
                    "hint_tags": [slug] if slug else [],
                    "weight": 1.0,
                    "description": (
                        spec.get("layout_description")
                        or "AI-generated template from mockup."
                    ),
                    "html": html,
                    "image_slots": image_slots,
                    "has_logo_slot": has_logo,
                    "source": "ai",
                    "is_active": True,
                },
            )
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "completed", result={"template_id": template_id, "family": family}
            )
        log.info("[agent_jobs] Template %s created from image", template_id)
    except Exception as e:
        log.error("[agent_jobs] Template job %s failed: %s", job_id, e, exc_info=True)
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "failed", error=str(e)
            )


async def _run_design_system_job(job_id: str, payload: dict) -> None:
    from app.services.brand_agent import create_design_system_from_input

    pool = await get_shared_session_factory()
    async with pool() as session:
        await AgentJobRepository(session).update_status(job_id, "running")

    try:
        result = await create_design_system_from_input(pool, payload)
        async with pool() as session:
            await AgentJobRepository(session).update_status(job_id, "completed", result=result)
        log.info("[agent_jobs] Design system %s created", result.get("design_system_id"))
    except Exception as e:
        log.error("[agent_jobs] Design-system job %s failed: %s", job_id, e, exc_info=True)
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "failed", error=str(e)
            )


@celery_app.task(bind=True, max_retries=0, acks_late=True)
def run_template_from_image(self, job_id: str, payload: dict):
    asyncio.run(_run_template_job(job_id, payload))


@celery_app.task(bind=True, max_retries=0, acks_late=True)
def run_design_system_from_input(self, job_id: str, payload: dict):
    asyncio.run(_run_design_system_job(job_id, payload))


async def _run_template_build_job(job_id: str, payload: dict) -> None:
    """Create a validated template from an image, HTML, and/or a text brief.

    One-shot (no chat): the agent authors a template from the supplied context,
    validates it (render + overflow + deterministic QC, retrying on critique),
    and saves the Template row. The job completes with the template id.
    """
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_systems import DEFAULT_ID
    from app.services.template_author import (
        author_template_html,
        build_layout_spec,
        validate_template_html,
    )
    from app.services.templates import scan_template_features

    pool = await get_shared_session_factory()

    async with pool() as session:
        await AgentJobRepository(session).update_status(job_id, "running")

    ds_id = payload.get("design_system_id") or DEFAULT_ID
    async with pool() as session:
        ds = await DesignSystemRepository(session).get_by_id(ds_id)
    if ds is None:
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "failed", error=f"Design system {ds_id!r} not found"
            )
        return

    family = payload.get("family") or "square"
    if family not in ("square", "portrait", "story", "landscape"):
        family = "square"
    ground = payload.get("ground") or "white"
    if ground not in ("white", "black"):
        ground = "white"

    message = (payload.get("message") or "").strip()
    source_html = (payload.get("html") or "").strip()
    image_b64 = payload.get("image") or ""
    mime = payload.get("mime") or "image/png"

    try:
        spec: dict = {"family": family, "ground": ground}
        if image_b64:
            image_bytes = base64.b64decode(image_b64)
            spec = await build_layout_spec(image_bytes, mime)
            family = spec.get("family") if spec.get("family") in ("square", "portrait", "story", "landscape") else family
            ground = spec.get("ground") if spec.get("ground") in ("white", "black") else ground
            spec["family"] = family
            spec["ground"] = ground
        elif message:
            spec = {
                "family": family,
                "ground": ground,
                "layout_description": message,
            }
        elif source_html:
            spec = {
                "family": family,
                "ground": ground,
                "layout_description": "Convert the provided HTML into a validated template.",
            }

        html = await author_template_html(
            spec, ds, ground_hint=ground, source_html=source_html
        )
        result = await validate_template_html(html, family, ds, ground)
        for _ in range(2):
            if result["ok"]:
                break
            html = await author_template_html(
                spec, ds, critique=result["critique"], ground_hint=ground,
                source_html=source_html,
            )
            result = await validate_template_html(html, family, ds, ground)
        if not result["ok"]:
            async with pool() as session:
                await AgentJobRepository(session).update_status(
                    job_id, "failed",
                    error="Template failed validation: " + "; ".join(result["issues"][:5]),
                )
            return

        import re as _re

        slug = _re.sub(r"[^a-z0-9]+", "-", (spec.get("layout_description") or message or "ai").lower())
        slug = _re.sub(r"^-+|-+$", "", slug)[:32]
        template_id = f"{ds.id}-{slug or 'ai'}"
        image_slots, has_logo = scan_template_features(html)

        from app.db.repositories.templates import TemplateRepository

        async with pool() as session:
            tpl_repo = TemplateRepository(session)
            base = template_id
            n = 2
            while await tpl_repo.get_by_id(template_id):
                template_id = f"{base}-{n}"
                n += 1
            await tpl_repo.create(
                {
                    "id": template_id,
                    "design_system_id": ds.id,
                    "name": slug or "AI template",
                    "family": family,
                    "grounds": (
                        [ground]
                        if 'data-ground="black"' not in html
                        else ["white", "black"]
                    ),
                    "categories": ["WRITING"],
                    "hint_tags": [slug] if slug else [],
                    "weight": 1.0,
                    "description": (
                        spec.get("layout_description")
                        or (message or "AI-generated template.")
                    ),
                    "html": html,
                    "image_slots": image_slots,
                    "has_logo_slot": has_logo,
                    "source": "ai",
                    "is_active": True,
                },
            )
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "completed", result={"template_id": template_id, "family": family}
            )
        log.info("[agent_jobs] Template %s created", template_id)
    except Exception as e:
        log.error("[agent_jobs] Template build job %s failed: %s", job_id, e, exc_info=True)
        async with pool() as session:
            await AgentJobRepository(session).update_status(
                job_id, "failed", error=str(e)
            )


@celery_app.task(bind=True, max_retries=0, acks_late=True)
def run_template_build_task(self, job_id: str, payload: dict):
    asyncio.run(_run_template_build_job(job_id, payload))
