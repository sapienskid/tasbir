import base64
import io
import logging
import os
import re
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.core.keylock import KeyedLocks
from app.core.limits import MAX_UPLOAD_B64
from app.core.ratelimit import interactive
from app.core.time import iso_utc
from app.db.repositories.tasks import TaskRepository
from app.services.artifacts import (
    delete_task_output,
    list_output_files,
    resolve_output_file,
)
from app.services.formats import get_format_info, validate_platforms

log = logging.getLogger(__name__)

router = APIRouter()


def is_manual_task(task) -> bool:
    """True for tasks created by Manual Compose (ADR-0021)."""
    return (task.source_data or {}).get("mode") == "manual"


@router.get("")
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    repo = TaskRepository(db)
    tasks = await repo.list(limit=limit, offset=offset, status=status)
    return [
        {
            "id": t.id,
            "title": (t.source_data or {}).get("title", ""),
            "status": t.status,
            "created_at": iso_utc(t.created_at),
        }
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    return {
        "id": task.id,
        "status": task.status,
        "source_data": task.source_data,
        "result": task.result,
        "edited_html": task.edited_html,
        "composition": task.composition,
        "progress": task.progress,
        "error": task.error,
        "created_at": iso_utc(task.created_at),
        "updated_at": iso_utc(task.updated_at),
    }


@router.get("/{task_id}/progress")
async def get_task_progress(task_id: str, db: AsyncSession = Depends(get_db)):
    """Live pipeline progress: {pct, node, per_format, done, total}.

    While running, per-format state is derived from the audit timeline; once
    settled, it comes from the stored result.
    """
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")

    progress = task.progress or {}
    pct = int(progress.get("pct", 0))
    node = str(progress.get("node", "pending"))

    if task.status in ("completed", "failed"):
        platforms = (
            ((task.result or {}).get("platforms") or {})
            if task.status == "completed"
            else {}
        )
        per_format = {
            fmt: {"status": str(p.get("status", "unknown"))}
            for fmt, p in platforms.items()
        }
        pct = 100 if task.status == "completed" else pct
        return {
            "pct": pct,
            "node": node,
            "per_format": per_format,
            "done": sum(1 for v in per_format.values() if v["status"] == "verified"),
            "total": len(per_format),
        }

    from app.db.repositories.audit_logs import AuditLogRepository

    rows = await AuditLogRepository(db).list_by_task(task_id)
    per_format: dict[str, dict] = {}
    for r in rows:
        dec = r.decision or {}
        fmt = dec.get("format")
        if not fmt:
            continue
        per_format[fmt] = {
            "step": r.agent_name,
            "status": str(dec.get("status") or "running"),
        }
    total = len(per_format)
    done = sum(1 for v in per_format.values() if v["status"] == "verified")
    if total:
        pct = max(pct, 50 + int(50 * done / total))
    return {
        "pct": pct,
        "node": node,
        "per_format": per_format,
        "done": done,
        "total": total,
    }


@router.get("/{task_id}/files")
async def list_task_files(task_id: str, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    if not await repo.get_by_id(task_id):
        raise NotFoundError(f"Task {task_id} not found")
    return list_output_files(task_id)


@router.get("/{task_id}/audit")
async def list_task_audit(task_id: str, db: AsyncSession = Depends(get_db)):
    """Per-agent step timeline for a task (strategist/copywriter + per-format chain)."""
    from app.db.repositories.audit_logs import AuditLogRepository

    repo = TaskRepository(db)
    if not await repo.get_by_id(task_id):
        raise NotFoundError(f"Task {task_id} not found")
    rows = await AuditLogRepository(db).list_by_task(task_id)
    return [
        {
            "id": r.id,
            "agent_name": r.agent_name,
            "decision": r.decision,
            "critique": r.critique,
            "created_at": iso_utc(r.created_at),
        }
        for r in rows
    ]


@router.get("/{task_id}/files/archive")
async def download_task_archive(task_id: str, db: AsyncSession = Depends(get_db)):
    """Download every remaining artifact (HTML + PNG) as a ZIP."""
    from app.services.artifacts import task_output_dir

    repo = TaskRepository(db)
    if not await repo.get_by_id(task_id):
        raise NotFoundError(f"Task {task_id} not found")

    base = task_output_dir(task_id)
    files = list_output_files(task_id)
    if not files:
        raise NotFoundError(f"No output files remain for task {task_id}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            path = base / f["filename"]
            if path.is_file():
                zf.write(path, arcname=f["filename"])
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{task_id}.zip"',
        },
    )


@router.get("/{task_id}/files/{filename}")
async def download_task_file(
    task_id: str,
    filename: str,
    consume: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Stream an artifact. Files persist until the TTL sweep by default.

    ``?consume=true`` streams then deletes (one-time download); the
    ``DELETE_ON_DOWNLOAD`` env flips the default.
    """
    from app.config import get_settings

    repo = TaskRepository(db)
    if not await repo.get_by_id(task_id):
        raise NotFoundError(f"Task {task_id} not found")
    try:
        path = resolve_output_file(task_id, filename)
    except FileNotFoundError:
        raise NotFoundError(f"File {filename!r} not found")

    delete_after = (
        consume if consume is not None else get_settings().delete_on_download
    )
    media_type = "image/png" if path.suffix.lower() == ".png" else "text/html; charset=utf-8"
    if delete_after:
        return FileResponse(
            path,
            media_type=media_type,
            filename=path.name,
            background=BackgroundTask(os.unlink, str(path)),
        )
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    delete_task_output(task_id)
    await db.delete(task)
    await db.commit()


class RerenderRequest(BaseModel):
    html: str = Field(min_length=50, max_length=500_000)


class SaveTemplateRequest(BaseModel):
    name: str = Field(default="", max_length=64)
    mode: str = Field(default="new", pattern="^(new|update)$")


@router.post("/{task_id}/formats/{fmt_id}/rerender")
async def rerender_format(
    task_id: str,
    fmt_id: str,
    request: RerenderRequest,
    audit: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Render an operator-edited HTML doc for a format and report QC.

    Serialized with the structured editor's refill per (task, format).
    """
    async with _FORMAT_LOCKS.hold((task_id, fmt_id)):
        return await _rerender_impl(task_id, fmt_id, request, audit, db)


async def _rerender_impl(
    task_id: str,
    fmt_id: str,
    request: RerenderRequest,
    audit: bool,
    db: AsyncSession,
):
    """Render an operator-edited HTML doc for a format and report QC.

    Skips the designer LLM — the HTML is taken as-is, sanitized, re-injected
    with tokens/fonts/KaTeX, rendered to PNG, and checked. Vision audit only
    runs when ``?audit=true`` to protect the free-tier quota.
    """
    from app.services.agents import get_agent_config
    from app.services.composer import finalize_html, katex_missing, run_hard_checks
    from app.services.dom_extractor import render_to_png
    from app.services.ds_context import (
        DSResolutionError,
        effective_design_system_id,
        resolve_ds_context_strict,
    )
    from app.services.sanitizer import sanitize_html

    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")

    validated = validate_platforms([fmt_id])
    fmt_id = validated[0]
    fmt = get_format_info(fmt_id)

    # Resolve the design system the format renders under (per-format editor
    # override, else the task's) + its per-post language override, so
    # re-render + QC use the right tokens/brand. Strict: unknown/inactive
    # systems or languages are a 422, never a silent default render.
    source = task.source_data or {}
    try:
        ctx = await resolve_ds_context_strict(
            db, effective_design_system_id(task, fmt_id), source.get("style_language") or ""
        )
    except DSResolutionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    tokens = ctx.tokens
    design_instruction = ctx.design_instruction
    footer = ctx.footer
    brief = ((task.result or {}).get("strategic_brief") or {})
    category = source.get("category") or brief.get("category") or ""
    ground = brief.get("ground", "white")

    html = sanitize_html(request.html, mode="preserve_system")
    html = finalize_html(
        html, ctx, source.get("images") or [], katex=katex_missing(html), logo=False
    )

    # Deterministic checks + overflow + low-contrast (no LLM cost)
    from app.agents.orchestrator.nodes.quality_check import (
        _build_design_system_context,
        _call_vision_llm,
        _extract_json,
    )

    issues = await run_hard_checks(html, ctx, fmt.width, fmt.height, category)

    passed = not issues
    score = 100 if passed else 20
    critique = "No issues." if passed else "Fix: " + "; ".join(issues)

    if audit and passed:
        try:
            prompt_cfg = await get_agent_config("verifier")
            png = await render_to_png(html, fmt.width, fmt.height)
            if png:
                ds_context = _build_design_system_context(
                    tokens, design_instruction, footer, category, ground
                )
                user_prompt = (
                    f"TARGET PLATFORM: {fmt_id} ({fmt.width}x{fmt.height}px)\n"
                    f"EXPECTED GROUND: {ground}\n{ds_context}\n\n"
                    "Audit this design image. Score 0-100 and provide actionable critique.\n"
                    'Return ONLY valid JSON: '
                    '{"pass": bool, "score": int, "issues": [...], "critique": "..."}'
                )
                raw = await _call_vision_llm(
                    system_prompt=prompt_cfg.system_prompt,
                    user_prompt=user_prompt,
                    image_bytes=png,
                    temperature=prompt_cfg.temperature,
                    max_tokens=prompt_cfg.max_tokens,
                )
                result = _extract_json(raw)
                passed = bool(result.get("pass", True))
                score = int(result.get("score", 75))
                issues = list(result.get("issues", []))
                critique = str(result.get("critique", ""))
        except Exception as e:
            issues = [f"Vision audit failed: {e}"]

    png_bytes = await _render_png_safe(html, fmt.width, fmt.height)
    if not png_bytes:
        issues.append(
            "PNG render unavailable — the HTML was saved; re-render to regenerate the image"
        )
        passed = False
        score = min(score, 40)

    # The HTML is the source of truth — always persisted (atomically) even if
    # the PNG render failed, so an edit is never lost to a render-service
    # hiccup. The edited HTML also lands in the DB so it survives file
    # consumption and reloads. A raw-HTML edit invalidates the structured
    # editor's remembered toggles/media, so those reset to "unknown".
    saved = await _persist_format(
        db,
        task_id,
        fmt_id,
        html,
        png_bytes,
        {
            "status": "verified" if passed else "needs_review",
            "quality_score": score,
            "quality_issues": issues,
        },
        {"hidden": None, "media_kind": None, "media": None},
        stamp_key="rerendered_at",
    )

    return {
        "format": fmt_id,
        "pass": passed,
        "quality": {"score": score, "issues": issues, "critique": critique},
        "png_b64": base64.b64encode(png_bytes).decode("ascii") if png_bytes else "",
        "html": html,
        "revision": saved["revision"],
        "saved_at": saved["saved_at"],
    }


def _build_resume_state(task) -> dict:
    """Reconstruct pipeline state from a failed run's stored result.

    Feeds back the strategic brief, post plan, per-format copy (and carousel
    base copy) so the strategist/planner/copywriter LLM steps are skipped on
    retry, and only unverified formats are re-designed.
    """
    from app.services.formats import parse_carousel_slide

    result = task.result or {}
    brief = result.get("strategic_brief") or {}
    post_plan = result.get("post_plan") or {}
    source = task.source_data or {}

    resume_tasks: dict[str, dict] = {}
    for fmt_id, r in (result.get("platforms") or {}).items():
        if parse_carousel_slide(fmt_id):
            continue  # the base carousel copy covers the slide set
        resume_tasks[fmt_id] = {
            "copy": r.get("copy", ""),
            "status": r.get("status"),
            "html_path": r.get("html_path", ""),
            "quality_score": r.get("quality_score", 0),
            "quality_issues": r.get("quality_issues", []),
            "template_id": r.get("template_id"),
            "error": r.get("error"),
        }
    for base_id, copy_json in (result.get("carousel_bases") or {}).items():
        resume_tasks[base_id] = {"copy": copy_json, "status": "copy_ready"}

    return {
        "strategic_brief": brief,
        "post_plan": post_plan,
        "category": brief.get("category") or source.get("category") or "",
        "ground": brief.get("ground") or "white",
        "platforms": post_plan.get("platforms") or source.get("platforms") or [],
        "slides": int(post_plan.get("slides") or 0),
        "sequence_check": result.get("sequence_check") or {},
        "format_tasks": resume_tasks,
    }


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Re-run a failed task, resuming from where it failed.

    Pre-seeds the pipeline with the stored strategic brief, post plan, and
    per-format copy, so the strategist/planner/copywriter LLM steps are skipped.
    Formats that already verified keep their artifacts; only unverified formats
    are re-designed and re-checked. Manual (composed) tasks simply re-run the
    deterministic compose job — no AI step is ever involved.
    """
    from app.tasks.generate import generate_task

    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")

    if is_manual_task(task):
        from app.tasks.compose import compose_task

        await repo.update_status(task_id=task_id, status="pending")
        compose_task.delay(task_id)
        return {"task_id": task_id, "status": "pending"}

    resume = _build_resume_state(task)
    source = dict(task.source_data or {})
    source["resume_state"] = resume
    await repo.save_source_data(task_id=task_id, source_data=source)
    await repo.update_status(task_id=task_id, status="pending")
    generate_task.delay(task_id, source)
    return {"task_id": task_id, "status": "pending"}


@router.post("/{task_id}/formats/{fmt_id}/retry")
async def retry_format(
    task_id: str,
    fmt_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-run the designer LLM for one format, then re-verify (full audit).

    A fresh design attempt with the previous verifier critique fed back — the
    manual retry for formats left in ``needs_retry`` / ``needs_review``.
    """
    from app.config import get_settings
    from app.services.format_retry import run_retry

    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")
    if is_manual_task(task):
        raise HTTPException(
            status_code=422,
            detail="Manually composed posts have no AI designer — edit the composition "
            "or the HTML instead",
        )

    validated = validate_platforms([fmt_id])
    fmt_id = validated[0]
    try:
        result = await run_retry(db, task, fmt_id, get_settings())
    except RuntimeError as e:
        msg = str(e)
        # Bad references (deleted/deactivated system, language, campaign) are
        # client errors; missing copy / busy state stays 409.
        if (
            "unknown design system" in msg
            or "is inactive" in msg
            or "unknown campaign" in msg
            or "Unknown design language" in msg
        ):
            raise HTTPException(status_code=422, detail=msg)
        raise HTTPException(status_code=409, detail=msg)
    return result


@router.post("/{task_id}/formats/{fmt_id}/template")
async def save_as_template(
    task_id: str,
    fmt_id: str,
    request: SaveTemplateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Promote a rendered/edited post into the design system's template library.

    Reads the current [data-slot] content from the saved HTML, converts it to
    a Jinja2 template, validates it (render + overflow), and stores it in the
    DB — as a new template (mode=new) or an update of the source template
    the post was built from (mode=update).
    """
    from app.services.artifacts import resolve_output_file
    from app.services.formats import get_format_info, validate_platforms
    from app.services.templates import (
        build_template_context,
        extract_slots,
        format_family,
        render_template_html,
        scan_template_features,
        slotize_html,
    )

    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")

    validated = validate_platforms([fmt_id])
    fmt_id = validated[0]
    fmt = get_format_info(fmt_id)

    # Prefer the DB-persisted edited HTML (survives file consumption); fall
    # back to the filesystem copy.
    html = ((task.edited_html or {}).get(fmt_id)) or None
    if html is None:
        try:
            html_path = resolve_output_file(task_id, f"{fmt_id}.html")
        except FileNotFoundError:
            raise NotFoundError(f"No HTML for {fmt_id} — render it first")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()

    from app.db.repositories.templates import TemplateRepository

    tpl_repo = TemplateRepository(db)
    platform = ((task.result or {}).get("platforms") or {}).get(fmt_id, {})
    source_template = platform.get("template_id") or ""
    design_system_id = (task.source_data or {}).get("design_system_id") or "default"
    family = format_family(fmt_id)

    if request.mode == "update":
        if not source_template:
            raise HTTPException(status_code=422, detail="This post was not built from a template")
        template_id = source_template
        existing = await tpl_repo.get_by_id(template_id)
        if not existing:
            raise HTTPException(
                status_code=422, detail=f"Source template {template_id!r} not found"
            )
        design_system_id = existing.design_system_id
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", (request.name or fmt_id).strip().lower())
        slug = slug.strip("-")
        if not slug:
            raise HTTPException(status_code=422, detail="Provide a template name")
        template_id = f"{family}-{slug}"
        # Ensure the id is unique within the design system.
        base = template_id
        suffix = 2
        while await tpl_repo.get_by_id(template_id):
            template_id = f"{base}-{suffix}"
            suffix += 1

    slots = extract_slots(html)
    if not slots:
        raise HTTPException(status_code=422, detail="No data-slot elements found in the HTML")

    template_html = slotize_html(html)

    # Validate before committing: render with the extracted copy, then check
    # overflow. Nothing is persisted on failure.
    from app.db.repositories.design_systems import DesignSystemRepository

    ds_row = await DesignSystemRepository(db).get_by_id(design_system_id)
    di_config = (ds_row.design_instruction or {}) if ds_row else {}
    copy = {
        "headline": slots.get("headline", ""),
        "subhead": slots.get("subhead", ""),
        "body": slots.get("body", ""),
        "badge": None,
    }
    context = build_template_context(
        copy,
        slots.get("kicker", ""),
        "black" if 'data-ground="black"' in html else "white",
        {"left": slots.get("footer_left", ""), "right": slots.get("footer_right", "")},
        fmt.width,
        fmt.height,
        False,
        seed=template_id,
        di_config=di_config,
    )
    from app.services.dom_extractor import detect_overflow

    try:
        rendered = render_template_html(template_html, context)
        overflow = await detect_overflow(rendered, fmt.width, fmt.height)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Template render failed: {e}")
    if overflow:
        raise HTTPException(
            status_code=422,
            detail="Template overflows the canvas: " + "; ".join(overflow),
        )

    image_slots, has_logo_slot = scan_template_features(template_html)
    data = {
        "design_system_id": design_system_id,
        "name": slots.get("footer_right", "") or request.name or template_id,
        "family": family,
        "grounds": ["white", "black"] if 'data-ground="black"' in html else ["white"],
        "categories": [slots.get("kicker", "").upper()] if slots.get("kicker") else [],
        "hint_tags": [slots.get("kicker", "").lower()] if slots.get("kicker") else [],
        "weight": 1.0,
        "description": f"Promoted from task {task_id[:8]} ({fmt_id}).",
        "html": template_html,
        "image_slots": image_slots,
        "has_logo_slot": has_logo_slot,
        "source": "promoted",
        "is_active": True,
    }

    if request.mode == "update":
        await tpl_repo.update(template_id, data)
    else:
        await tpl_repo.create({**data, "id": template_id})

    return {"template_id": template_id, "mode": request.mode, "file": f"db://{template_id}"}



# ---------------------------------------------------------------------------
# Structured editing (ADR-0022 refill, ADR-0023 instant preview)
# ---------------------------------------------------------------------------

# One lock per (task, format) serializes the read-latest → build → render →
# write → persist sequence, so quick successive edits merge instead of the last
# writer winning. A second, per-task lock guards only the short DB
# read-modify-write of the JSON columns (``result`` / ``edited_html`` are
# shared by every format of a carousel).
_FORMAT_LOCKS = KeyedLocks()
_TASK_LOCKS = KeyedLocks()

_MAX_SLOTS = 32
_MAX_HIDDEN = 64
# Shared with /api/compose — one cap for every base64 image upload.
_MAX_UPLOAD_B64 = MAX_UPLOAD_B64
_COPY_FIELDS = ("headline", "subhead", "body", "tagline")
_MEDIA_META_KEYS = ("url", "credit", "photographer", "provider", "license", "style", "seed", "alt")


class RefillRequest(BaseModel):
    """Structured content edit for a template-built format (no raw HTML).

    ``slots`` maps data-slot names (headline, subhead, body, …) to new text.
    ``hidden`` / ``media_position`` / ``template_id`` / ``media`` trigger a
    full template re-fill; otherwise only the slot texts are swapped in place
    (media, illustration, and counters are preserved exactly). A
    ``template_id`` on a post that has none converts a designer-LLM post.
    """

    slots: dict[str, str] = Field(default_factory=dict)
    hidden: list[str] | None = Field(default=None, max_length=_MAX_HIDDEN)
    media_position: str = Field(default="auto", max_length=16)
    template_id: str = Field(default="", max_length=64)
    # Media change (same shape as Manual Compose media): upload / photo /
    # illustration. Omitted = keep the post's baked media untouched.
    media: dict | None = None
    # Re-fill under another design system (template is remapped, tokens/fonts/
    # footer/logo come from the new system). Omitted = the format's current
    # system (a previous switch) or the task's.
    design_system_id: str = Field(default="", max_length=64)


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _platform_entries(task) -> dict:
    return _as_dict(_as_dict(task.result).get("platforms"))


def _read_latest_html(task, fmt_id: str) -> str | None:
    """The format's current document: DB-persisted edit first, else the file."""
    html = _as_dict(task.edited_html).get(fmt_id)
    if isinstance(html, str) and html.strip():
        return html
    try:
        path = resolve_output_file(task.id, f"{fmt_id}.html")
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None


def _stored_copy_flat(entry: dict) -> dict[str, str]:
    """The persisted per-format copy JSON as flat slot names (``extra.x``)."""
    import json

    try:
        data = json.loads(entry.get("copy") or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    flat = {k: str(data[k]) for k in _COPY_FIELDS if data.get(k)}
    for k, v in _as_dict(data.get("extra")).items():
        if v:
            flat[f"extra.{k}"] = str(v)
    return flat


def _illustration_styles() -> list[str]:
    from app.services.tools.illustrator import ILLUSTRATE_TOOL

    return ILLUSTRATE_TOOL["function"]["parameters"]["properties"]["style"]["enum"]


def _normalize_media(media: dict, kinds: list[str]) -> dict:
    """Validate a request ``media`` object against what the template can host.

    Returns a normalized copy (an upload's mime is the sniffed one). Raises
    typed 422s — never lets bad media reach the renderer.
    """
    import base64
    import binascii
    import re

    kind = str(media.get("kind") or "")
    if kind not in ("upload", "photo", "illustration"):
        raise HTTPException(
            status_code=422, detail="media.kind must be upload, photo, or illustration"
        )
    if kind in ("upload", "photo") and "image" not in kinds:
        raise HTTPException(status_code=422, detail="This template has no image slot")
    if kind == "illustration" and "illustration" not in kinds:
        raise HTTPException(status_code=422, detail="This template has no illustration slot")
    out = {**media, "kind": kind}
    if kind == "upload":
        data = str(media.get("data") or "")
        if not data:
            raise HTTPException(status_code=422, detail="Upload is empty")
        if len(data) > _MAX_UPLOAD_B64:
            raise HTTPException(status_code=422, detail="Upload too large")
        from app.services.uploads import validate_upload

        try:
            stripped = re.sub(r"^data:[^,]*;base64,", "", data.strip())
            raw = base64.b64decode(re.sub(r"\s+", "", stripped), validate=True)
            mime, b64 = validate_upload(raw)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(status_code=422, detail=f"Invalid upload — {e}") from e
        # The sniffed type wins over the declared one (it lands in a data: URI).
        out["data"], out["mime"] = b64, mime
    elif kind == "photo":
        if not str(media.get("url") or "").startswith("https://"):
            raise HTTPException(status_code=422, detail="Photo needs an https url")
    else:
        style = str(media.get("style") or "procedural")
        if style not in _illustration_styles():
            raise HTTPException(
                status_code=422, detail=f"Unknown illustration style {style!r}"
            )
    return out


def _media_meta(media: dict) -> dict:
    """The persistable, base64-free description of a media choice."""
    meta = {"kind": media.get("kind") or "none"}
    for key in _MEDIA_META_KEYS:
        value = media.get(key)
        if isinstance(value, str) and value:
            meta[key] = value[:300]
    if meta["kind"] == "upload" and media.get("mime"):
        meta["mime"] = str(media["mime"])[:40]
    return meta


def _derive_media(html: str, template_html: str) -> dict:
    """Best-effort media description of an already-rendered document."""
    from app.services.templates import extract_baked_images, extract_baked_photo, media_kinds

    photo = extract_baked_photo(html)
    if photo:
        meta = {"kind": "photo"}
        if photo.get("credit"):
            meta["credit"] = photo["credit"][:300]
        return meta
    if "data-image-key" in html and "base64" in html and extract_baked_images(html):
        return {"kind": "upload"}
    if "<svg" in html and "illustration" in media_kinds(template_html or ""):
        return {"kind": "illustration"}
    return {"kind": "none"}


async def _build_refill(task, fmt_id: str, request: RefillRequest, db: AsyncSession):
    """Compute a structured edit's finalized document — the ONE fill routine.

    Shared by ``POST …/refill/preview`` (returns the document) and
    ``POST …/refill`` (also hard-checks, renders, and persists it), so the
    preview is byte-for-byte what a save stores. Validation + status codes
    live here. Reads the latest document (DB edit, else file) and writes
    nothing. Returns ``(html, meta)``.
    """
    from app.db.repositories.templates import TemplateRepository
    from app.services.composer import (
        fetch_photo,
        fill_template,
        finalize_html,
        katex_missing,
        render_illustration,
    )
    from app.services.design_instruction import photo_grayscale
    from app.services.ds_context import DSResolutionError, resolve_ds_context_strict
    from app.services.formats import parse_carousel_slide
    from app.services.html_payloads import hoist_data_uris, restore_data_uris
    from app.services.sanitizer import sanitize_html
    from app.services.templates import (
        CONTENT_FIELDS,
        VALID_MEDIA_POSITIONS,
        detect_elements,
        extract_baked_images,
        extract_baked_photo,
        extract_slots,
        format_family,
        media_kinds,
        replace_slots,
    )

    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")
    if is_manual_task(task):
        raise HTTPException(
            status_code=422,
            detail="Manually composed posts edit via PUT /tasks/{task_id}/composition instead",
        )

    fmt_id = validate_platforms([fmt_id])[0]
    fmt = get_format_info(fmt_id)

    if len(request.slots) > _MAX_SLOTS:
        raise HTTPException(status_code=422, detail=f"At most {_MAX_SLOTS} slots per refill")
    for name, value in request.slots.items():
        if len(name) > 64 or len(value) > 5000:
            raise HTTPException(status_code=422, detail=f"Slot {name!r} exceeds size limits")
    if request.media_position not in VALID_MEDIA_POSITIONS:
        raise HTTPException(
            status_code=422,
            detail=f"media_position must be one of {sorted(VALID_MEDIA_POSITIONS)}",
        )

    entry = _platform_entries(task).get(fmt_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Format {fmt_id!r} is not part of this task")
    entry = _as_dict(entry)
    source = _as_dict(task.source_data)
    prev_editor = _as_dict(entry.get("editor"))
    current_ds = (
        str(prev_editor.get("design_system_id") or "")
        or str(source.get("design_system_id") or "")
        or "default"
    )
    requested_ds = request.design_system_id.strip()
    target_ds = requested_ds or current_ds
    ds_switching = bool(requested_ds and requested_ds != current_ds)
    if requested_ds:
        from app.db.repositories.design_systems import DesignSystemRepository

        row = await DesignSystemRepository(db).get_by_id(requested_ds)
        if row is None:
            raise HTTPException(
                status_code=422, detail=f"Unknown design system {requested_ds!r}"
            )
        if not row.is_active:
            raise HTTPException(
                status_code=422, detail=f"Design system {requested_ds!r} is inactive"
            )
    current_template = str(entry.get("template_id") or "")
    requested_template = request.template_id.strip()
    target_template = requested_template or current_template
    remapped: dict[str, str] | None = None
    if ds_switching and not requested_template:
        # Same template id only survives when the target system owns that row;
        # otherwise the closest match (same scoring as Manual Compose's map).
        from app.services.templates import (
            default_template,
            match_template,
            template_to_dict,
        )

        brief_early = _as_dict(_as_dict(task.result).get("strategic_brief"))
        ground_early = brief_early.get("ground", "white")
        if ground_early not in ("white", "black"):
            ground_early = "white"
        tpl_repo = TemplateRepository(db)
        keep = await tpl_repo.get_by_id(current_template) if current_template else None
        if keep is not None and keep.design_system_id == target_ds:
            target_template = current_template
        else:
            family = format_family(fmt_id)
            targets = [
                template_to_dict(r) for r in await tpl_repo.list(target_ds, family=family)
            ]
            if current_template and keep is not None:
                best = match_template(template_to_dict(keep), targets)
            else:
                best = default_template(targets, family, ground_early)
            if best is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Design system {target_ds!r} has no {family} template to switch to",
                )
            remapped = {"from": current_template, "to": str(best["id"])}
            target_template = str(best["id"])
    if not target_template:
        raise HTTPException(
            status_code=422,
            detail="This post has no template — pick a template to convert it, "
            "or edit the HTML instead",
        )
    switching = bool(target_template != current_template)
    converted = not current_template
    full = (
        switching
        or ds_switching
        or request.hidden is not None
        or request.media_position != "auto"
        or request.media is not None
    )

    # The template row is only needed to *re-fill*; a text-only edit of a post
    # whose template was since deleted still works (it swaps slot text in place).
    row = await TemplateRepository(db).get_by_id(target_template)
    if row is None and (full or switching):
        raise HTTPException(
            status_code=422,
            detail=f"Template {target_template!r} not found — pick another template",
        )
    if row is not None and row.design_system_id != target_ds:
        raise HTTPException(
            status_code=422,
            detail=f"Template {target_template!r} does not belong to design system "
            f"{target_ds!r}",
        )
    if row is not None and row.family != format_family(fmt_id):
        raise HTTPException(
            status_code=422,
            detail=f"Template {target_template!r} is {row.family}, not {format_family(fmt_id)}",
        )
    template_html = (row.html or "") if row is not None else ""
    kinds = media_kinds(template_html)

    if request.hidden is not None:
        known = set(detect_elements(template_html))
        unknown = [h for h in request.hidden if h not in known]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown hidden element(s) {unknown} — valid: {sorted(known)}",
            )
    req_media = _normalize_media(request.media, kinds) if request.media is not None else None

    prior_html = _read_latest_html(task, fmt_id)
    if prior_html is None:
        raise HTTPException(status_code=404, detail=f"No HTML for {fmt_id} — render it first")
    # Structural passes run on a "light" copy with the (opaque, possibly
    # multi-MB) base64 image payloads swapped for tokens — see html_payloads.
    light, payloads = hoist_data_uris(prior_html)

    try:
        ctx = await resolve_ds_context_strict(
            db, target_ds, source.get("style_language") or ""
        )
    except DSResolutionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    brief = _as_dict(_as_dict(task.result).get("strategic_brief"))
    category = source.get("category") or brief.get("category") or ""
    ground = brief.get("ground", "white")
    if ground not in ("white", "black"):
        ground = "white"

    # Layered copy: the stored copy (keeps text of currently-hidden slots),
    # then what the document renders now, then the edit itself.
    merged = _stored_copy_flat(entry)
    merged.update(extract_slots(light))
    merged.update(request.slots)

    editor = {
        "hidden": prev_editor.get("hidden"),
        "media_position": prev_editor.get("media_position") or "auto",
        "media_kind": prev_editor.get("media_kind"),
        "media": prev_editor.get("media"),
        "design_system_id": target_ds,
    }

    if full:
        seed = f"{source.get('title', '')}|{fmt_id}"
        gray = photo_grayscale(ctx.design_instruction)
        images: list[dict] = []
        photo: dict | None = None
        illustration: str | None = None
        has_image = False
        media_state: dict = {"kind": "none"}
        if req_media is not None and req_media["kind"] == "upload":
            images = [
                {
                    "data": req_media["data"],
                    "mime": req_media["mime"],
                    "alt": str(req_media.get("alt") or "")[:300],
                }
            ]
            has_image = True
            illustration = ""  # never a procedural figure on top of a real image
            media_state = _media_meta(req_media)
        elif req_media is not None and req_media["kind"] == "photo":
            try:
                image = await fetch_photo(req_media)
            except Exception as e:  # noqa: BLE001 — a flaky provider is a typed error
                log.warning("[refill] photo fetch failed: %s", e)
                image = None
            if image is None:
                raise HTTPException(status_code=422, detail="Stock photo could not be downloaded")
            photo = {"image": image, "credit": str(req_media.get("credit") or "")}
            has_image = True
            illustration = ""
            media_state = _media_meta(req_media)
        elif req_media is not None:
            style = str(req_media.get("style") or "procedural")
            fig_seed = str(req_media.get("seed") or f"{seed}|media")
            illustration = render_illustration(style, fig_seed, ground)
            media_state = {"kind": "illustration", "style": style, "seed": fig_seed}
        else:
            # No media in the request: carry the post's current media over so a
            # text / toggle / template edit never drops the art.
            prev_media = _as_dict(prev_editor.get("media"))
            baked_photo = extract_baked_photo(light) if "image" in kinds else None
            baked = (
                extract_baked_images(light)
                if "image" in kinds and baked_photo is None and payloads
                else []
            )
            if baked_photo:
                baked_photo["image"]["data"] = restore_data_uris(
                    baked_photo["image"]["data"], payloads
                )
                photo = baked_photo
                has_image = True
                illustration = ""
                media_state = {"kind": "photo", **{
                    k: v for k, v in prev_media.items()
                    if k != "kind" and prev_media.get("kind") == "photo"
                }}
                if baked_photo.get("credit"):
                    media_state["credit"] = baked_photo["credit"][:300]
            elif baked:
                images = [
                    {**b, "data": restore_data_uris(b["data"], payloads)} for b in baked
                ]
                has_image = True
                illustration = ""
                media_state = {"kind": "upload"}
            elif prev_media.get("kind") == "illustration" and "illustration" in kinds:
                style = str(prev_media.get("style") or "procedural")
                if style in _illustration_styles():
                    fig_seed = str(prev_media.get("seed") or f"{seed}|media")
                    illustration = render_illustration(style, fig_seed, ground)
                    media_state = {"kind": "illustration", "style": style, "seed": fig_seed}
        copy = {
            "headline": merged.get("headline", ""),
            "subhead": merged.get("subhead", ""),
            "body": merged.get("body", ""),
            "tagline": merged.get("tagline", ""),
            "extra": {k[6:]: v for k, v in merged.items() if k.startswith("extra.") and v},
            "badge": None,
        }
        hidden = request.hidden if request.hidden is not None else (row.hidden_elements or [])
        media_position = (
            request.media_position
            if request.media_position != "auto"
            else (row.media_position or "auto")
        )
        parsed = parse_carousel_slide(fmt_id)
        slide_index, slide_total = (parsed[1], 0) if parsed else (0, 0)
        if parsed:
            keys = _platform_entries(task)
            slide_total = len([p for p in keys if p.startswith(f"{parsed[0]}-")])
            slide_total = slide_total or int(source.get("slides") or 0)
        try:
            filled = fill_template(
                template_html,
                copy=copy,
                kicker=merged.get("kicker", "") or category,
                ground=ground,
                footer=ctx.footer,
                width=fmt.width,
                height=fmt.height,
                has_image=has_image,
                seed=seed,
                family=format_family(fmt_id),
                logo=ctx.logo,
                di_config=ctx.design_instruction,
                illustration=illustration,
                slide_index=slide_index,
                slide_total=slide_total,
                media_position=media_position,
                hidden=hidden,
                photo=photo,
                grayscale=gray,
            )
        except Exception as e:  # noqa: BLE001 — a broken template is the operator's to fix
            raise HTTPException(
                status_code=422, detail=f"Template render failed: {e}"
            ) from e
        # (a photo embedded by fill_template is big too — sanitize the light copy)
        light_filled, filled_payloads = hoist_data_uris(filled)
        html = sanitize_html(light_filled, mode="strict")
        html = finalize_html(html, ctx, images or None, grayscale=gray)
        if parsed and slide_total > 0:
            from app.agents.orchestrator.nodes.renderer import inject_slide_counter

            html = inject_slide_counter(html, slide_index, slide_total)
        # Slots are read off the light copy (fast); payloads go back last.
        final_slots = extract_slots(hoist_data_uris(html)[0])
        html = restore_data_uris(html, filled_payloads)
        editor = {
            "hidden": list(hidden),
            # The request's value (not the resolved default) so the round trip
            # through GET …/editor is idempotent.
            "media_position": request.media_position,
            "media_kind": media_state["kind"],
            "media": media_state,
            "design_system_id": target_ds,
        }
    else:
        if not request.slots:
            raise HTTPException(status_code=422, detail="Provide at least one slot")
        html, replaced = replace_slots(light, request.slots)
        # A slot whose element is currently hidden has no node to swap, but its
        # text is still stored (it reappears when the element is shown again).
        accepted = set(replaced) | {n for n in request.slots if n in CONTENT_FIELDS}
        if not accepted:
            raise HTTPException(
                status_code=422,
                detail=f"No matching data-slot found — available: "
                f"{sorted(extract_slots(light))}",
            )
        html = sanitize_html(html, mode="preserve_system")
        html = finalize_html(
            html, ctx, source.get("images") or [], katex=katex_missing(html), logo=False
        )
        final_slots = extract_slots(hoist_data_uris(html)[0])
        html = restore_data_uris(html, payloads)

    if not html.strip():
        raise HTTPException(status_code=422, detail="Rendering produced an empty document")

    meta = {
        "fmt_id": fmt_id,
        "width": fmt.width,
        "height": fmt.height,
        "template_id": target_template,
        "converted": converted,
        "full": full,
        "slots": final_slots,
        "copy": {
            "headline": merged.get("headline", ""),
            "subhead": merged.get("subhead", ""),
            "body": merged.get("body", ""),
            "tagline": merged.get("tagline", ""),
            "extra": {k[6:]: v for k, v in merged.items() if k.startswith("extra.") and v},
            "badge": None,
        },
        "editor": editor,
        "prior_html": prior_html,
        "category": category,
        "ground": ground,
        "ctx": ctx,
        "row": row,
        "design_system_id": target_ds,
        "ds_switched": ds_switching,
        "remapped": remapped,
    }
    return html, meta


def _public_editor(editor: dict) -> dict:
    """The (base64-free) editor-state subset returned by preview."""
    return {
        "hidden": editor.get("hidden"),
        "media_position": editor.get("media_position") or "auto",
        "media_kind": editor.get("media_kind"),
        "media": editor.get("media"),
    }


@router.post("/{task_id}/formats/{fmt_id}/refill/preview")
@interactive
async def refill_preview(
    task_id: str,
    fmt_id: str,
    request: RefillRequest,
    db: AsyncSession = Depends(get_db),
):
    """The finalized document a refill would produce — nothing is rendered or saved.

    Same validation and status codes as ``…/refill`` (they share
    ``_build_refill``), but no hard checks, no PNG, no file or DB writes, no
    render-service call: this is the editor's instant-preview path.
    """
    task = await TaskRepository(db).get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    html, meta = await _build_refill(task, fmt_id, request, db)
    return {
        "html": html,
        "width": meta["width"],
        "height": meta["height"],
        "template_id": meta["template_id"],
        "slots": meta["slots"],
        "converted": meta["converted"],
        "editor": _public_editor(meta["editor"]),
        "design_system_id": meta["design_system_id"],
        "remapped": meta["remapped"],
    }


async def _persist_format(
    db: AsyncSession,
    task_id: str,
    fmt_id: str,
    html: str,
    png_bytes: bytes | None,
    entry_patch: dict,
    editor_patch: dict,
    *,
    designer_backup: str | None = None,
    stamp_key: str = "refilled_at",
) -> dict:
    """Write a format's artifacts atomically, then update the task row.

    Files first (temp + ``os.replace``, so a reader never sees a half-written
    file), DB second. The DB step is a per-task read-modify-write on a fresh
    row so concurrent edits of *other* formats of the same task are kept.
    Returns ``{revision, saved_at, entry}``. Raises typed HTTP errors.
    """
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy.exc import SQLAlchemyError

    from app.config import get_settings
    from app.services.artifacts import atomic_write

    out_dir = os.path.join(get_settings().output_dir, task_id)
    html_path = os.path.join(out_dir, f"{fmt_id}.html")
    png_path = os.path.join(out_dir, f"{fmt_id}.png")
    try:
        os.makedirs(out_dir, exist_ok=True)
        if designer_backup is not None:
            backup_path = os.path.join(out_dir, f"{fmt_id}.designer.html")
            # Never overwrite an earlier backup with a later (converted) doc.
            if not os.path.exists(backup_path):
                await asyncio.to_thread(atomic_write, backup_path, designer_backup)
        # The HTML is the source of truth — always persist it, even when the
        # PNG render failed, so an edit is never lost to a render-service hiccup.
        await asyncio.to_thread(atomic_write, html_path, html)
        if png_bytes:
            await asyncio.to_thread(atomic_write, png_path, png_bytes)
    except OSError as e:
        log.error("[editor] writing outputs for %s/%s failed: %s", task_id, fmt_id, e)
        raise HTTPException(
            status_code=500, detail=f"Could not write the output files: {e}"
        ) from e

    saved_at = datetime.now(timezone.utc).isoformat()
    repo = TaskRepository(db)
    try:
        async with _TASK_LOCKS.hold(task_id):
            fresh = await repo.get_fresh(task_id)
            if fresh is None:
                raise HTTPException(status_code=404, detail=f"Task {task_id} was deleted")
            if fresh.status in ("pending", "running"):
                raise HTTPException(
                    status_code=409, detail="Task started processing again — edit not saved"
                )
            result = dict(_as_dict(fresh.result))
            platforms = dict(_as_dict(result.get("platforms")))
            prev = _as_dict(platforms.get(fmt_id))
            revision = int(_as_dict(prev.get("editor")).get("revision") or 0) + 1
            entry = {
                **prev,
                **entry_patch,
                "html_path": html_path,
                stamp_key: saved_at,
                "editor": {**_as_dict(prev.get("editor")), **editor_patch, "revision": revision},
            }
            platforms[fmt_id] = entry
            result["platforms"] = platforms
            edited = dict(_as_dict(fresh.edited_html))
            edited[fmt_id] = html
            await repo.save_format_state(task_id, result, edited)
    except SQLAlchemyError as e:
        log.error("[editor] DB update for %s/%s failed: %s", task_id, fmt_id, e)
        raise HTTPException(status_code=500, detail=f"Could not save the edit: {e}") from e
    return {"revision": revision, "saved_at": saved_at, "entry": entry}


async def _render_png_safe(html: str, width: int, height: int) -> bytes | None:
    from app.services.dom_extractor import render_to_png

    try:
        return await render_to_png(html, width, height)
    except Exception as e:  # noqa: BLE001 — the HTML is saved regardless
        log.warning("[editor] PNG render raised: %s", e)
        return None


def _editor_payload(
    *,
    task,
    fmt_id: str,
    entry: dict,
    row,
    html: str | None,
    editable: bool,
    convertible: bool,
    reason: str | None,
) -> dict:
    """The editor-state document (``GET …/editor`` and the refill response)."""
    from app.services.templates import (
        detect_elements,
        detect_fields,
        extract_slots,
        format_family,
        media_kinds,
    )

    fmt = get_format_info(fmt_id)
    source = _as_dict(task.source_data)
    brief = _as_dict(_as_dict(task.result).get("strategic_brief"))
    ground = brief.get("ground", "white")
    template_html = (row.html or "") if row is not None else ""
    persisted = _as_dict(entry.get("editor"))

    slots = _stored_copy_flat(entry)
    if html:
        slots.update(extract_slots(html))
    media = persisted.get("media")
    if not isinstance(media, dict) or not media.get("kind"):
        media = _derive_media(html, template_html) if html else {"kind": "none"}
    hidden = persisted.get("hidden")
    return {
        "editable": editable,
        "convertible": convertible,
        "reason": reason,
        "template_id": str(entry.get("template_id") or ""),
        "family": format_family(fmt_id),
        "ground": ground if ground in ("white", "black") else "white",
        "width": fmt.width,
        "height": fmt.height,
        "slots": slots,
        "hidden": list(hidden) if isinstance(hidden, list) else None,
        "media_position": persisted.get("media_position") or "auto",
        "media": media,
        "media_kinds": media_kinds(template_html),
        "revision": int(persisted.get("revision") or 0),
        "design_system_id": str(persisted.get("design_system_id") or "")
        or str(source.get("design_system_id") or "")
        or "default",
        "style_language": source.get("style_language") or "",
        # Additive: what the template renders / can toggle (drives the form).
        "fields": detect_fields(template_html),
        "elements": detect_elements(template_html),
    }


@router.get("/{task_id}/formats/{fmt_id}/editor")
@interactive
async def get_editor_state(
    task_id: str,
    fmt_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Everything the structured editor needs to (re)open a format.

    Restores the state that only ever lived in the UI's memory: element
    toggles, media position and media kind survive a reload (persisted on
    every refill). Designer-LLM posts report ``editable=false,
    convertible=true, reason="designer"``; manual tasks ``reason="manual"``.
    """
    from app.db.repositories.templates import TemplateRepository

    task = await TaskRepository(db).get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    fmt_id = validate_platforms([fmt_id])[0]
    entry = _platform_entries(task).get(fmt_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Format {fmt_id!r} is not part of this task")
    entry = _as_dict(entry)

    template_id = str(entry.get("template_id") or "")
    row = await TemplateRepository(db).get_by_id(template_id) if template_id else None
    html = _read_latest_html(task, fmt_id)

    if task.status in ("pending", "running"):
        editable, convertible, reason = False, False, "running"
    elif is_manual_task(task):
        editable, convertible, reason = False, False, "manual"
    elif not template_id:
        convertible = html is not None or bool(entry.get("copy"))
        editable, reason = False, "designer"
    elif row is None:
        editable, convertible, reason = False, True, "template_missing"
    elif html is None:
        editable, convertible, reason = False, False, "expired"
    else:
        editable, convertible, reason = True, False, None
    return _editor_payload(
        task=task,
        fmt_id=fmt_id,
        entry=entry,
        row=row,
        html=html,
        editable=editable,
        convertible=convertible,
        reason=reason,
    )


@router.post("/{task_id}/formats/{fmt_id}/refill")
@interactive
async def refill_format(
    task_id: str,
    fmt_id: str,
    request: RefillRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply a structured slot edit to a template-built format and re-render.

    Text-only edits swap ``[data-slot]`` content in the current HTML (zero
    LLM, media preserved). Element toggles, media position, media, or a
    template switch re-fill the template deterministically, preserving baked
    media. A ``template_id`` on a designer-LLM post converts it to a template
    post (the original is kept as ``{fmt}.designer.html``). Runs the
    deterministic hard gate (no vision audit) and persists like a rerender.

    Serialized per (task, format): the latest document is re-read under the
    lock so concurrent edits of different slots merge. The response carries
    the finalized ``html`` + ``revision`` so the client never refetches.
    """
    import base64
    import json

    async with _FORMAT_LOCKS.hold((task_id, fmt_id)):
        repo = TaskRepository(db)
        task = await repo.get_fresh(task_id)
        if not task:
            raise NotFoundError(f"Task {task_id} not found")
        html, meta = await _build_refill(task, fmt_id, request, db)
        fmt_id = meta["fmt_id"]
        width, height = meta["width"], meta["height"]

        try:
            from app.services.composer import run_hard_checks

            issues = await run_hard_checks(html, meta["ctx"], width, height, meta["category"])
        except Exception as e:  # noqa: BLE001 — checks are advisory; never lose the edit
            log.warning("[refill] hard checks failed for %s/%s: %s", task_id, fmt_id, e)
            issues = [f"Automatic checks unavailable: {e}"]
        passed = not issues
        score = 100 if passed else 20
        critique = "No issues." if passed else "Fix: " + "; ".join(issues)

        png_bytes = await _render_png_safe(html, width, height)
        if not png_bytes:
            issues.append(
                "PNG render unavailable — the HTML was saved; re-render to regenerate the image"
            )
            passed = False
            score = min(score, 40)

        editor = meta["editor"]
        media_kind = editor.get("media_kind")
        media = editor.get("media")
        if not media_kind:  # text-only edit of a never-refilled post → describe it now
            row = meta["row"]
            media = _derive_media(html, (row.html or "") if row is not None else "")
            media_kind = media["kind"]
        patch = {
            "status": "verified" if passed else "needs_review",
            "quality_score": score,
            "quality_issues": issues,
            "template_id": meta["template_id"],
            "copy": json.dumps(meta["copy"]),
        }
        if meta["converted"]:
            patch["converted_from"] = "designer"
            patch["designer_backup"] = f"{fmt_id}.designer.html"
        saved = await _persist_format(
            db,
            task_id,
            fmt_id,
            html,
            png_bytes,
            patch,
            {
                "hidden": editor.get("hidden"),
                "media_position": editor.get("media_position") or "auto",
                "media_kind": media_kind,
                "media": media,
                "design_system_id": meta["design_system_id"],
            },
            designer_backup=meta["prior_html"] if meta["converted"] else None,
        )
        entry = saved["entry"]
        return {
            "format": fmt_id,
            "pass": passed,
            "quality": {"score": score, "issues": issues, "critique": critique},
            "png_b64": base64.b64encode(png_bytes).decode("ascii") if png_bytes else "",
            "template_id": meta["template_id"],
            "html": html,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "editor": _editor_payload(
                task=task,
                fmt_id=fmt_id,
                entry=entry,
                row=meta["row"],
                html=html,
                editable=True,
                convertible=False,
                reason=None,
            ),
            "converted": meta["converted"],
            "slots": meta["slots"],
            "design_system_id": meta["design_system_id"],
            "remapped": meta["remapped"],
        }
