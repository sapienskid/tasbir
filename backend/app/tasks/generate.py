"""Celery generate task — runs the LangGraph pipeline, outputs HTML + PNG.
"""

import asyncio
import logging

from app.agents.orchestrator.graph import run_pipeline
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
            from app.services.design_systems import load_ds_templates
            from app.services.ds_context import (
                DSResolutionError,
                resolve_ds_context_strict,
            )
            from app.services.image_loader import prepare_images
            from app.services.tokens import DEFAULT_TOKEN_VALUES

            settings = get_settings()

            # Design system drives tokens, brand, footer, categories, campaigns,
            # design-instruction, and the logo. Defaults to the seeded system.
            # A per-post design-language override applies the language's rules
            # + palette to THIS post only (in-memory), without changing the DS.
            # Strict: unknown/inactive systems, languages, or campaigns fail
            # the task loudly instead of silently rendering the wrong brand.
            override = str(source_data.get("style_language") or "")
            try:
                ctx = await resolve_ds_context_strict(
                    pool, source_data.get("design_system_id") or "default", override
                )
            except DSResolutionError as e:
                async with pool() as session:
                    await TaskRepository(session).update_status(
                        task_id=task_id, status="failed", error=str(e),
                    )
                from app.agents.orchestrator.post_cache import post_cache_clear as _pcc

                _pcc(task_id)
                return
            if ctx.style_language:
                log.info("[generate] %s uses per-post language override %r", task_id, override)

            # Setup pipeline input
            pipeline_input = dict(source_data)
            pipeline_input["_task_id"] = task_id
            pipeline_input.update(
                {
                    "design_system_id": ctx.ds_id,
                    "design_tokens": ctx.tokens or dict(DEFAULT_TOKEN_VALUES),
                    "token_roles": ctx.token_roles,
                    "brand_info": ctx.brand,
                    "footer": ctx.footer,
                    "categories": ctx.categories,
                    "design_instruction": ctx.design_instruction,
                    "logo": ctx.logo,
                    "logo_variants": ctx.logo_variants,
                }
            )

            # Overrides: brand/system-level, then API request (highest priority)
            request_overrides = source_data.get("overrides", {}) or {}
            pipeline_input["overrides"] = {
                **(ctx.overrides or {}),
                **request_overrides,
            }

            # Campaign preset from this design system's campaigns map.
            # Strict: an unknown campaign fails loudly (no silent default).
            campaign_name = source_data.get("campaign", "default")
            campaigns = ctx.campaigns or {}
            if campaign_name not in campaigns:
                async with pool() as session:
                    await TaskRepository(session).update_status(
                        task_id=task_id,
                        status="failed",
                        error=f"Unknown campaign {campaign_name!r} for design system {ctx.ds_id!r}",
                    )
                from app.agents.orchestrator.post_cache import post_cache_clear as _pcc2

                _pcc2(task_id)
                return
            pipeline_input["campaign"] = campaigns.get(
                campaign_name, campaigns.get("default", {})
            )
            pipeline_input["campaign_name"] = campaign_name

            # Category override from API request (highest priority)
            if source_data.get("category"):
                pipeline_input["category"] = source_data["category"]

            # The design system's active template library (selection input).
            pipeline_input["ds_templates"] = await load_ds_templates(pool, ctx.ds_id)
            pipeline_input["template_id"] = source_data.get("template_id") or ""
            pipeline_input["platforms_config"] = source_data.get("platforms_config") or {}
            pipeline_input["template_mode"] = source_data.get("template_mode") or "auto"
            pipeline_input["post_type"] = source_data.get("post_type") or "default"
            pipeline_input["verbatim"] = bool(source_data.get("verbatim"))

            # Effective illustration style: API override → DS default → procedural.
            from app.services.design_systems import resolve_illustration_style

            pipeline_input["illustration_style"] = resolve_illustration_style(
                ctx.design_instruction or {},
                str(source_data.get("illustration_style") or ""),
            )

            # Download URL images / pass through uploaded base64 media.
            raw_images = source_data.get("images", [])
            if not raw_images:
                # Auto-discover web images from markdown content: ![alt](https://...)
                import re
                discovered = []
                content_text = source_data.get("content", "") or ""
                for match in re.finditer(r"!\[(.*?)\]\((https?://[^\s)]+)\)", content_text):
                    alt = match.group(1).strip()
                    url = match.group(2).strip()
                    discovered.append({"url": url, "alt": alt, "placement": "auto"})
                if discovered:
                    raw_images = discovered[:8]
                    log.info(
                        "[generate_task] Auto-discovered %d markdown image(s) from content",
                        len(raw_images),
                    )

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

            from app.services.format_recipe import FormatRecipe, parse_copy, recipe_json
            from app.services.formats import is_carousel_base

            def _recipe_for(fmt_id: str, ft: dict) -> dict:
                """Self-contained per-format recipe (see services/format_recipe).

                Ground/language/category used to live only at task level, which
                is why a format could not carry its own. They are copied in here
                once, at generation time, and are authoritative from then on.
                """
                _copy_d = parse_copy(ft.get("copy"))
                return recipe_json(
                    FormatRecipe(
                        origin="template" if ft.get("template_id") else "designer",
                        template_id=str(ft.get("template_id") or ""),
                        design_system_id=str(source_data.get("design_system_id") or ""),
                        style_language=str(source_data.get("style_language") or ""),
                        ground=(
                            brief.get("ground")
                            if brief.get("ground") in ("white", "black")
                            else "white"
                        ),
                        category=str(
                            source_data.get("category") or brief.get("category") or ""
                        ),
                        headline=str(_copy_d.get("headline") or ""),
                        subhead=str(_copy_d.get("subhead") or ""),
                        body=str(_copy_d.get("body") or ""),
                        tagline=str(_copy_d.get("tagline") or ""),
                        extra=dict(_copy_d.get("extra") or {}),
                    )
                )

            platform_results = {
                fmt_id: {
                    "status": ft.get("status", "unknown"),
                    "quality_score": ft.get("quality_score", 0),
                    "quality_issues": ft.get("quality_issues", []),
                    "html_path": ft.get("html_path", ""),
                    "template_id": ft.get("template_id"),
                    "error": ft.get("error"),
                    "copy": ft.get("copy", ""),
                    "recipe": _recipe_for(fmt_id, ft),
                    **({"copy_qa": (state.get("copy_qa") or {}).get(fmt_id)}
                       if (state.get("copy_qa") or {}).get(fmt_id) else {}),
                    **({"publish": (state.get("publish") or {}).get(fmt_id)}
                       if (state.get("publish") or {}).get(fmt_id) else {}),
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
                        "copy_qa": state.get("copy_qa") or {},
                        "copy_qa_blocked": state.get("copy_qa_blocked") or [],
                        "publish": state.get("publish") or {},
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
