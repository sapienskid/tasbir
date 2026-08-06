"""Celery generate task — runs the LangGraph pipeline, outputs HTML + PNG.
"""

import asyncio
import logging

from app.agents.orchestrator.graph import run_pipeline
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def generate_task(self, task_id: str, source_data: dict):
    async def _run():
        pool = await get_shared_session_factory()

        # Workers don't run the FastAPI lifespan — refresh config caches so
        # DB edits (platforms/fonts/settings) apply without a restart.
        from app.services.fonts import refresh_font_pool
        from app.services.platforms import refresh_platforms
        from app.services.settings import refresh_runtime_settings

        await refresh_platforms(pool)
        await refresh_font_pool(pool)
        await refresh_runtime_settings(pool)

        async with pool() as session:
            repo = TaskRepository(session)
            await repo.update_status(task_id=task_id, status="running")

        async def _execute() -> None:

            from app.config import get_settings
            from app.services.design_systems import build_pipeline_payload, load_ds_templates
            from app.services.image_loader import prepare_images
            from app.services.tokens import DEFAULT_TOKEN_VALUES

            settings = get_settings()

            # Design system drives tokens, brand, footer, categories, campaigns,
            # design-instruction, and the logo. Defaults to the seeded system.
            ds_id = source_data.get("design_system_id") or "default"
            async with pool() as session:
                ds = await DesignSystemRepository(session).get_by_id(ds_id)
                if ds is None:
                    log.warning(
                        "[generate_task] Design system %r not found — falling back to default",
                        ds_id,
                    )
                    async with pool() as s2:
                        ds = await DesignSystemRepository(s2).get_by_id("default")
                if ds is None:
                    raise RuntimeError("No design system available (seed failed)")

            payload = build_pipeline_payload(ds)

            # Setup pipeline input
            pipeline_input = dict(source_data)
            pipeline_input["_task_id"] = task_id
            pipeline_input.update(
                {
                    "design_system_id": ds.id,
                    "design_tokens": payload["design_tokens"]
                    or dict(DEFAULT_TOKEN_VALUES),
                    "token_roles": payload["token_roles"],
                    "brand_info": payload["brand_info"],
                    "footer": payload["footer"],
                    "categories": payload["categories"],
                    "design_instruction": payload["design_instruction"],
                    "logo": payload["logo"],
                }
            )

            # Overrides: brand/system-level, then API request (highest priority)
            request_overrides = source_data.get("overrides", {}) or {}
            pipeline_input["overrides"] = {
                **(payload.get("overrides") or {}),
                **request_overrides,
            }

            # Campaign preset from this design system's campaigns map.
            campaign_name = source_data.get("campaign", "default")
            campaigns = payload.get("campaigns") or {}
            pipeline_input["campaign"] = campaigns.get(
                campaign_name, campaigns.get("default", {})
            )
            pipeline_input["campaign_name"] = campaign_name

            # Category override from API request (highest priority)
            if source_data.get("category"):
                pipeline_input["category"] = source_data["category"]

            # The design system's active template library (selection input).
            pipeline_input["ds_templates"] = await load_ds_templates(pool, ds.id)
            pipeline_input["template_id"] = source_data.get("template_id") or ""
            pipeline_input["platforms_config"] = source_data.get("platforms_config") or {}
            pipeline_input["template_mode"] = source_data.get("template_mode") or "auto"
            pipeline_input["post_type"] = source_data.get("post_type") or "default"
            pipeline_input["verbatim"] = bool(source_data.get("verbatim"))

            # Per-post design-language override: apply the language's rules + palette
            # to THIS post only (in-memory), without changing the design system.
            override = str(source_data.get("style_language") or "")
            if override:
                async with pool() as session:
                    from app.services.design_languages import apply_language, get_language

                    lang = await get_language(session, override)
                    if lang is not None:
                        di = await apply_language(
                            session, override, payload.get("design_instruction") or {}
                        )
                        tokens = dict(pipeline_input["design_tokens"])
                        for var, value in (lang.palette_tokens or {}).items():
                            tokens[var] = value
                        for var, value in (lang.accent_tokens or {}).items():
                            tokens[var] = value
                        pipeline_input["design_instruction"] = di
                        pipeline_input["design_tokens"] = tokens
                        log.info(
                            "[generate] %s uses per-post language override %r", task_id, override
                        )
                    else:
                        log.warning(
                            "[generate] unknown style_language override %r ignored", override
                        )

            # Effective illustration style: API override → DS default → procedural.
            from app.services.design_systems import resolve_illustration_style

            pipeline_input["illustration_style"] = resolve_illustration_style(
                payload.get("design_instruction") or {},
                str(source_data.get("illustration_style") or ""),
            )

            # Download URL images / pass through uploaded base64 media.
            raw_images = source_data.get("images", [])
            pipeline_input["images"] = await prepare_images(raw_images) if raw_images else []
            raw_platform_images = source_data.get("platform_images", {}) or {}
            pipeline_input["platform_images"] = {
                pid: (await prepare_images(imgs) if imgs else [])
                for pid, imgs in raw_platform_images.items()
            }

            try:
                last_pct = {"value": -1}

                async def _on_progress(pct: int, label: str) -> None:
                    if pct == last_pct["value"]:
                        return
                    last_pct["value"] = pct
                    try:
                        async with pool() as session:
                            await TaskRepository(session).save_progress(
                                task_id, {"pct": pct, "node": label}
                            )
                    except Exception as e:  # noqa: BLE001
                        log.warning("[generate_task] progress write failed: %s", e)

                state = await run_pipeline(
                    pipeline_input,
                    progress_callback=_on_progress,
                    resume_state=pipeline_input.get("resume_state"),
                )
            except Exception as e:
                log.error(
                    "[generate_task] Pipeline failed for task %s: %s",
                    task_id, e, exc_info=True,
                )
                async with pool() as session:
                    await TaskRepository(session).update_status(
                        task_id=task_id, status="failed", error=str(e),
                    )
                from app.agents.orchestrator.post_cache import post_cache_clear
                post_cache_clear(task_id)
                return

            from pathlib import Path

            from app.agents.orchestrator.post_cache import post_cache_clear

            post_cache_clear(task_id)

            output_dir = Path(settings.output_dir) / task_id

            output_paths = {}
            if output_dir.exists():
                for f in output_dir.iterdir():
                    if f.is_file():
                        fmt_id = f.stem
                        ext = f.suffix.lstrip(".")
                        output_paths.setdefault(fmt_id, {})[ext] = str(f)

            brief = state.get("strategic_brief", {})
            format_tasks = state.get("format_tasks", {})

            from app.services.formats import is_carousel_base

            platform_results = {
                fmt_id: {
                    "status": ft.get("status", "unknown"),
                    "quality_score": ft.get("quality_score", 0),
                    "quality_issues": ft.get("quality_issues", []),
                    "html_path": ft.get("html_path", ""),
                    "template_id": ft.get("template_id"),
                    "error": ft.get("error"),
                    "copy": ft.get("copy", ""),
                }
                for fmt_id, ft in format_tasks.items()
                # Carousel base entries only hold the slide copy — the slides
                # themselves (instagram-carousel-N / -portrait-N) are the outputs.
                if not (is_carousel_base(fmt_id) and not ft.get("html_path"))
            }
            # Carousel base copy is kept separately so a retry can re-expand the
            # slide set without re-running the copywriter.
            carousel_bases = {
                fmt_id: ft.get("copy", "")
                for fmt_id, ft in format_tasks.items()
                if is_carousel_base(fmt_id)
            }

            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=task_id,
                    status="completed",
                    result={
                        "output_paths": output_paths,
                        "strategic_brief": brief,
                        "post_plan": state.get("post_plan", {}),
                        "sequence_check": state.get("sequence_check", {}),
                        "platforms": platform_results,
                        "carousel_bases": carousel_bases,
                        "media_credits": state.get("media_credits") or [],
                    },
                )

            log.info("[generate_task] Task %s completed. Outputs: %s", task_id, output_paths)

        try:
            await _execute()
        except Exception as e:
            log.error(
                "[generate_task] Task %s failed during setup or pipeline: %s", task_id, e,
                exc_info=True,
            )
            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=task_id, status="failed", error=str(e),
                )
            from app.agents.orchestrator.post_cache import post_cache_clear
            post_cache_clear(task_id)

    asyncio.run(_run())
