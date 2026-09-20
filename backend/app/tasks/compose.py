"""Celery compose task — renders a Manual Compose post. Never calls an LLM.

For each slide of the task's stored composition: resolve the design-system
context (+ language override) → fill the chosen template (composer) →
finalize → render PNG → deterministic checks + overflow + low-contrast (the
same hard gate as the rerender endpoint; no vision audit). Artifacts and the
task result use exactly the shape the AI pipeline writes, so task detail,
editor, rerender, ZIP and save-as-template work unchanged (ADR-0021).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(bind=True, acks_late=True)
def compose_task(self, task_id: str):
    asyncio.run(run_compose(task_id))


async def _progress(pool, task_id: str, pct: int, node: str) -> None:
    try:
        async with pool() as session:
            await TaskRepository(session).save_progress(task_id, {"pct": pct, "node": node})
    except Exception as e:  # noqa: BLE001
        log.warning("[compose_task] progress write failed: %s", e)


async def _fail(pool, task_id: str, error: str) -> None:
    async with pool() as session:
        await TaskRepository(session).update_status(task_id=task_id, status="failed", error=error)


async def run_compose(task_id: str, pool=None) -> None:
    """Compose + render every slide of a manual task (the task body, testable)."""
    pool = pool or await get_shared_session_factory()

    # Workers don't run the FastAPI lifespan — refresh config caches so DB
    # edits (platforms/fonts/settings) apply without a restart.
    from app.services.fonts import refresh_font_pool
    from app.services.platforms import refresh_platforms
    from app.services.settings import refresh_runtime_settings

    await refresh_platforms(pool)
    await refresh_font_pool(pool)
    await refresh_runtime_settings(pool)

    async with pool() as session:
        task = await TaskRepository(session).get_by_id(task_id)
    if task is None:
        log.warning("[compose_task] task %s not found", task_id)
        return
    composition = task.composition or {}
    if not (composition.get("post") or {}).get("slides"):
        await _fail(pool, task_id, "Task has no composition to render")
        return

    async with pool() as session:
        await TaskRepository(session).update_status(task_id=task_id, status="running")
    await _progress(pool, task_id, 5, "compose")

    try:
        await _execute(pool, task_id, composition)
    except Exception as e:
        log.error("[compose_task] Task %s failed: %s", task_id, e, exc_info=True)
        await _fail(pool, task_id, str(e))


async def _execute(pool, task_id: str, composition: dict) -> None:
    from app.config import get_settings
    from app.db.repositories.templates import TemplateRepository
    from app.services import dom_extractor
    from app.services.artifacts import delete_task_output
    from app.services.composer import compose_slide, run_hard_checks
    from app.services.ds_context import resolve_ds_context
    from app.services.formats import carousel_slide_id, get_format_info, is_carousel_base
    from app.services.templates import template_to_dict

    settings = get_settings()
    post = composition.get("post") or {}
    platform = str(post.get("platform") or "")
    slides = list(post.get("slides") or [])
    ground = composition.get("ground")
    ground = ground if ground in ("white", "black") else "white"
    carousel = is_carousel_base(platform)
    total = len(slides)

    ctx = await resolve_ds_context(
        pool,
        composition.get("design_system_id") or "default",
        composition.get("style_language") or "",
    )

    templates: dict[str, dict] = {}
    async with pool() as session:
        repo = TemplateRepository(session)
        for slide in slides:
            tid = slide.get("template_id") or ""
            if tid and tid not in templates:
                row = await repo.get_by_id(tid)
                if row is not None:
                    templates[tid] = template_to_dict(row)

    # A re-compose replaces every artifact (a shorter carousel must not leave
    # stale slide files behind for the gallery to pick up).
    delete_task_output(task_id)
    out_dir = Path(settings.output_dir) / task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    platforms: dict[str, dict] = {}
    output_paths: dict[str, dict] = {}
    credits: list[dict] = []
    for i, slide in enumerate(slides, 1):
        fmt_id = carousel_slide_id(platform, i) if carousel else platform
        fmt = get_format_info(fmt_id)
        tid = slide.get("template_id") or ""
        copy_json = json.dumps(slide.get("copy") or {}, ensure_ascii=False)
        entry = {
            "status": "error",
            "quality_score": 0,
            "quality_issues": [],
            "html_path": "",
            "template_id": tid or None,
            "error": None,
            "copy": copy_json,
        }
        template = templates.get(tid)
        if template is None:
            entry["error"] = f"Template {tid!r} not found"
            platforms[fmt_id] = entry
            continue

        issues: list[str] = []
        try:
            html = await compose_slide(ctx, template, fmt_id, slide, i, total, ground, issues)
        except Exception as e:  # noqa: BLE001 — one broken slide never sinks the post
            log.warning("[compose_task] %s slide %d render failed: %s", task_id, i, e)
            entry["error"] = f"Template render failed: {e}"
            platforms[fmt_id] = entry
            continue

        issues.extend(await run_hard_checks(html, ctx, fmt.width, fmt.height))
        png = await dom_extractor.render_to_png(html, fmt.width, fmt.height)

        html_path = out_dir / f"{fmt_id}.html"
        html_path.write_text(html, encoding="utf-8")
        output_paths.setdefault(fmt_id, {})["html"] = str(html_path)
        passed = not issues
        score = 100 if passed else 20
        if png:
            png_path = out_dir / f"{fmt_id}.png"
            png_path.write_bytes(png)
            output_paths[fmt_id]["png"] = str(png_path)
        else:
            issues.append(
                "PNG render unavailable — the HTML was saved; re-render to regenerate the image"
            )
            passed = False
            score = min(score, 40)

        entry.update(
            {
                "status": "verified" if passed else "needs_review",
                "quality_score": score,
                "quality_issues": issues,
                "html_path": str(html_path),
            }
        )
        platforms[fmt_id] = entry

        media = slide.get("media") or {}
        if media.get("kind") == "photo":
            credits.append(
                {
                    "kind": "photo",
                    "provider": media.get("provider") or None,
                    "photographer": media.get("photographer") or None,
                    "license": media.get("license") or None,
                    "credit": media.get("credit") or "",
                }
            )
        await _progress(pool, task_id, 5 + int(90 * i / max(total, 1)), "compose")

    rendered = [f for f, p in platforms.items() if p.get("html_path")]
    result = {
        "output_paths": output_paths,
        # Manual posts have no strategist; the brief carries the ground so
        # rerender / audit read the right one.
        "strategic_brief": {"category": "", "ground": ground},
        "post_plan": {
            "post_type": "carousel" if carousel else "single",
            "platforms": [platform],
            "slides": total if carousel else 0,
        },
        "sequence_check": {},
        "platforms": platforms,
        "carousel_bases": {},
        "media_credits": credits,
    }
    async with pool() as session:
        repo = TaskRepository(session)
        if rendered:
            await repo.update_status(task_id=task_id, status="completed", result=result)
        else:
            errors = "; ".join(p.get("error") or "" for p in platforms.values() if p.get("error"))
            await repo.update_status(
                task_id=task_id,
                status="failed",
                result=result,
                error=f"Nothing rendered: {errors or 'no slides'}",
            )
    await _progress(pool, task_id, 100, "done")
    log.info("[compose_task] Task %s composed %d/%d slide(s)", task_id, len(rendered), total)
