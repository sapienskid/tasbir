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

        async with pool() as session:
            repo = TaskRepository(session)
            await repo.update_status(task_id=task_id, status="running")

        from app.config import get_settings
        from app.services.tokens import load_tokens, load_brand, load_campaign, load_brand_design, DEFAULT_TOKEN_VALUES
        from app.services.image_loader import prepare_images

        settings = get_settings()

        # Setup pipeline input
        pipeline_input = dict(source_data)
        pipeline_input["_task_id"] = task_id
        pipeline_input["design_tokens"] = load_tokens(settings.tokens_path) or dict(DEFAULT_TOKEN_VALUES)

        # Load brand profile
        brand_data = load_brand(settings.brand_path)
        pipeline_input["brand_info"] = brand_data.get("brand", {})
        pipeline_input["overrides"] = {**brand_data.get("overrides", {}), **source_data.get("overrides", {})}

        # Load brand footer + category taxonomy
        brand_design = load_brand_design(settings.brand_path)
        pipeline_input["footer"] = brand_design["footer"]
        pipeline_input["categories"] = brand_design["categories"]

        # Category override from API request (highest priority)
        if source_data.get("category"):
            pipeline_input["category"] = source_data["category"]

        # Load campaign preset by name (string) — fallback to "default"
        campaign_name = source_data.get("campaign", "default")
        campaign = load_campaign(campaign_name, settings.campaigns_path)
        pipeline_input["campaign"] = campaign
        pipeline_input["campaign_name"] = campaign_name

        # Download and prepare images
        raw_images = source_data.get("images", [])
        pipeline_input["images"] = await prepare_images(raw_images) if raw_images else []

        try:
            state = await run_pipeline(pipeline_input)
        except Exception as e:
            log.error("[generate_task] Pipeline failed for task %s: %s", task_id, e, exc_info=True)
            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=task_id, status="failed", error=str(e),
                )
            return

        from pathlib import Path

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

        platform_results = {
            fmt_id: {
                "status": ft.get("status", "unknown"),
                "quality_score": ft.get("quality_score", 0),
                "quality_issues": ft.get("quality_issues", []),
                "html_path": ft.get("html_path", ""),
                "error": ft.get("error"),
            }
            for fmt_id, ft in format_tasks.items()
        }

        async with pool() as session:
            await TaskRepository(session).update_status(
                task_id=task_id,
                status="completed",
                result={
                    "output_paths": output_paths,
                    "strategic_brief": brief,
                    "platforms": platform_results,
                },
            )

        log.info("[generate_task] Task %s completed. Outputs: %s", task_id, output_paths)

    asyncio.run(_run())
