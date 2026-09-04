"""Manual retry — re-run the designer LLM for one format with QC.

When a format ends in ``needs_retry`` (or ``needs_review`` after a re-render),
the operator can hit retry to get a FRESH LLM design attempt instead of only
editing the existing HTML. This rebuilds the per-format pipeline state
(designer → renderer → full verifier) exactly like the graph does, feeding the
previous verifier critique back so the new attempt fixes it.

Copy for the format is taken from the stored task result (``platforms[fmt].copy``,
persisted by generate_task) with a fallback to reading the current HTML's
``data-slot`` texts, so even older tasks can retry.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.agents.orchestrator.state import initial_state
from app.services.formats import get_format_info

log = logging.getLogger(__name__)


async def _ds_templates(db, ds_id: str) -> list[dict]:
    """The design system's templates as selection-ready dicts (uses the session)."""
    from app.db.repositories.templates import TemplateRepository
    from app.services.templates import template_to_dict

    rows = await TemplateRepository(db).list(ds_id)
    return [template_to_dict(r) for r in rows]


def _copy_from_slots(html: str) -> dict | None:
    """Best-effort copy reconstruction from the saved HTML's data-slot texts."""
    from app.services.templates import extract_slots

    if not html:
        return None
    slots = extract_slots(html)
    if not slots.get("headline"):
        return None
    return {
        "headline": slots.get("headline", ""),
        "subhead": slots.get("subhead", ""),
        "body": slots.get("body", ""),
        "tagline": slots.get("tagline", ""),
        "badge": None,
    }


def _stored_copy(result: dict, fmt_id: str) -> str | None:
    """The format's copy JSON from the task result, if persisted."""
    try:
        entry = (result or {}).get("platforms", {}).get(fmt_id) or {}
        copy = entry.get("copy") or ""
        if copy and json.loads(copy).get("headline"):
            return copy
    except Exception:  # noqa: BLE001
        pass
    return None


async def build_retry_state(db, task, fmt_id: str) -> dict | None:
    """Assemble a per-format GenerationState for a designer retry."""
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_systems import (
        build_pipeline_payload,
        resolve_illustration_style,
    )

    source = task.source_data or {}
    ds_id = source.get("design_system_id") or "default"
    ds = await DesignSystemRepository(db).get_by_id(ds_id)
    if ds is None:
        from app.db.session import get_shared_session_factory

        pool = await get_shared_session_factory()
        async with pool() as session:
            ds = await DesignSystemRepository(session).get_by_id("default")
        if ds is None:
            return None
    payload = build_pipeline_payload(ds)

    result = task.result or {}
    copy_json = _stored_copy(result, fmt_id)
    if not copy_json:
        html_file = Path((result or {}).get("output_paths", {}).get(fmt_id, {}).get("html", ""))
        if not html_file.is_file():
            from app.config import get_settings

            html_file = Path(get_settings().output_dir) / task.id / f"{fmt_id}.html"
        if html_file.is_file():
            slots_copy = _copy_from_slots(html_file.read_text(encoding="utf-8"))
            if slots_copy:
                copy_json = json.dumps(slots_copy)
    if not copy_json:
        return None

    try:
        from app.agents.orchestrator.nodes.copywriter import _clean_markdown

        c = json.loads(copy_json)
        c["headline"] = _clean_markdown(c.get("headline", ""))
        c["subhead"] = _clean_markdown(c.get("subhead", ""))
        c["body"] = _clean_markdown(c.get("body", ""))
        copy_json = json.dumps(c)
    except Exception:
        pass

    campaign_name = source.get("campaign", "default")
    campaigns = payload.get("campaigns") or {}
    campaign = campaigns.get(campaign_name, campaigns.get("default", {}))

    brief = result.get("strategic_brief") or {}
    category = source.get("category") or brief.get("category") or ""
    ground = brief.get("ground", "white")
    if ground not in ("white", "black"):
        ground = "white"
    footer = payload.get("footer") or {"left": "", "right": ""}

    from app.services.image_loader import prepare_images

    images = await prepare_images(source.get("images") or []) if source.get("images") else []

    overrides = {**(payload.get("overrides") or {}), **(source.get("overrides") or {})}

    state = initial_state(
        title=source.get("title", ""),
        content=source.get("content", ""),
        platforms=[fmt_id],
        _task_id=task.id,
        design_system_id=ds.id,
        excerpt=source.get("excerpt", ""),
        tags=source.get("tags", []),
        slides=int(source.get("slides") or 0),
        ratio=source.get("ratio", "square"),
        sequence_audit=bool(source.get("sequence_audit")),
        design_tokens=payload["design_tokens"],
        token_roles=payload["token_roles"],
        brand_info=payload["brand_info"],
        campaign=campaign,
        campaign_name=campaign_name,
        overrides=overrides,
        images=images,
        footer=footer,
        categories=payload["categories"],
        category=category,
        ground=ground,
        design_instruction=payload["design_instruction"],
        logo=payload["logo"],
        template_id=source.get("template_id") or "",
        ds_templates=await _ds_templates(db, ds.id),
        illustration_style=resolve_illustration_style(
            payload.get("design_instruction") or {},
            str(source.get("illustration_style") or ""),
        ),
        verbatim=bool(source.get("verbatim")),
    )

    from app.services.formats import parse_carousel_slide

    parsed_slide = parse_carousel_slide(fmt_id)
    if parsed_slide:
        base, idx = parsed_slide
        total = int(source.get("slides") or 0)
        if total <= 0:
            total = (
                len([p for p in (result.get("platforms") or {}) if p.startswith(f"{base}-")])
                or 1
            )
        state["slide_context"] = {
            fmt_id: {
                "index": idx,
                "total": total,
                "platform": base,
            }
        }
        slide_img_map = (source.get("platform_images") or {}).get(base, {})
        if slide_img_map:
            slot_img = slide_img_map.get(str(idx - 1)) or slide_img_map.get(str(idx))
            if slot_img:
                prep = await prepare_images([slot_img])
                if prep:
                    state["_slide_images"] = {fmt_id: prep}

    state["format_tasks"] = {
        fmt_id: {
            "status": "copy_ready",
            "copy": copy_json,
            "html": None,
            "html_path": None,
            "quality_score": 0,
            "quality_issues": [],
            "refinement_count": 0,
            "error": None,
            "template_id": None,
        }
    }
    state["_processing_format_id"] = fmt_id
    state["strategic_brief"] = brief
    # Feed the previous critique back so the new attempt fixes it.
    prev = (result or {}).get("platforms", {}).get(fmt_id) or {}
    state["verification"] = {
        fmt_id: {
            "critique": prev.get("quality_issues") and ("; ".join(prev["quality_issues"]))
            or prev.get("error")
            or "",
        }
    }
    state["retry_count"] = {fmt_id: 1}
    return state



async def run_retry(db, task, fmt_id: str, settings) -> dict:
    """Run designer → renderer → full verifier for one format. Returns result dict."""
    from datetime import datetime, timezone

    from app.agents.orchestrator.graph import _apply_updates
    from app.agents.orchestrator.nodes.designer import designer_node_single
    from app.agents.orchestrator.nodes.quality_check import quality_check_node_single
    from app.agents.orchestrator.nodes.renderer import renderer_node_single
    from app.db.repositories.tasks import TaskRepository

    fmt_id = get_format_info(fmt_id).id
    state = await build_retry_state(db, task, fmt_id)
    if state is None:
        raise RuntimeError(
            "Cannot retry — no stored copy and no renderable HTML to recover it from"
        )

    _apply_updates(state, await designer_node_single(state))
    _apply_updates(state, await renderer_node_single(state))
    _apply_updates(state, await quality_check_node_single(state))

    ft = state["format_tasks"][fmt_id]
    verification = state["verification"].get(fmt_id, {})
    status = ft.get("status", "")
    passed = status == "verified"
    score = int(ft.get("quality_score") or verification.get("score") or 0)
    issues = list(ft.get("quality_issues") or verification.get("issues") or [])
    critique = str(verification.get("critique") or "")

    out_dir = Path(settings.output_dir) / task.id
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = Path(ft.get("html_path") or out_dir / f"{fmt_id}.html")
    png_path = out_dir / f"{fmt_id}.png"
    html = ft.get("html") or (html_path.read_text(encoding="utf-8") if html_path.is_file() else "")
    if html:
        html_path.write_text(html, encoding="utf-8")

    # Reflect the retry in the stored task result.
    result = dict(task.result or {})
    platforms = dict(result.get("platforms") or {})
    platforms[fmt_id] = {
        **(platforms.get(fmt_id) or {}),
        "status": "verified" if passed else "needs_review",
        "quality_score": score,
        "quality_issues": issues,
        "html_path": str(html_path),
        "template_id": ft.get("template_id"),
        "error": ft.get("error"),
        "copy": ft.get("copy", ""),
        "retried_at": datetime.now(timezone.utc).isoformat(),
    }
    output_paths = dict(result.get("output_paths") or {})
    output_paths[fmt_id] = {"html": str(html_path), "png": str(png_path)}
    result["platforms"] = platforms
    result["output_paths"] = output_paths
    await TaskRepository(db).update_status(task_id=task.id, status=task.status, result=result)

    return {
        "format": fmt_id,
        "pass": passed,
        "score": score,
        "issues": issues,
        "critique": critique,
        "html_path": str(html_path),
        "png_path": str(png_path) if png_path.is_file() else None,
        "template_id": ft.get("template_id"),
    }
