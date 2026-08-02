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

    Skips the designer LLM — the HTML is taken as-is, sanitized, re-injected
    with tokens/fonts/KaTeX, rendered to PNG, and checked. Vision audit only
    runs when ``?audit=true`` to protect the free-tier quota.
    """
    from app.config import get_settings
    from app.services.agents import get_agent_config
    from app.services.design_instruction import (
        build_google_fonts_link,
        inject_fonts_into_html,
        substitute_image_keys,
    )
    from app.services.dom_extractor import detect_overflow, render_to_png
    from app.services.sanitizer import sanitize_html
    from app.services.tokens import (
        DEFAULT_TOKEN_VALUES,
        inject_katex_into_html,
        inject_tokens_into_html,
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

    settings = get_settings()
    # Resolve the design system the task was built with (DB first, YAML
    # fallback for legacy rows) so re-render + QC use the right tokens/brand.
    ds_id = (task.source_data or {}).get("design_system_id") or "default"
    payload: dict = {}
    try:
        from app.db.repositories.design_systems import DesignSystemRepository
        from app.services.design_systems import build_pipeline_payload

        ds = await DesignSystemRepository(db).get_by_id(ds_id)
        if ds is not None:
            payload = build_pipeline_payload(ds)
    except Exception as e:
        log.warning("[rerender] Design-system payload failed (%s) — default DS", e)
    if not payload:
        from app.services.design_systems import default_design_system_payload

        payload = await default_design_system_payload()
    tokens = payload.get("design_tokens") or dict(DEFAULT_TOKEN_VALUES)
    design_instruction = payload.get("design_instruction") or {}
    footer = payload.get("footer") or {"left": "", "right": ""}
    brief = ((task.result or {}).get("strategic_brief") or {})
    category = (task.source_data or {}).get("category") or brief.get("category") or ""
    ground = brief.get("ground", "white")

    html = sanitize_html(request.html, mode="preserve_system")
    if "cdn.jsdelivr.net/npm/katex" not in html:
        html = inject_katex_into_html(html)
    html = inject_tokens_into_html(html, tokens)
    html = inject_fonts_into_html(html, build_google_fonts_link(tokens, design_instruction))
    html = substitute_image_keys(html, (task.source_data or {}).get("images") or [])

    # Deterministic checks (no LLM cost)
    display_value = tokens.get("--font-display", "Space Grotesk, Inter, sans-serif")
    display_family = display_value.split(",")[0].strip()
    from app.agents.orchestrator.nodes.quality_check import (
        _build_design_system_context,
        _call_vision_llm,
        _extract_json,
        _run_deterministic_checks,
    )

    issues = _run_deterministic_checks(
        html, footer, category, fmt.width, fmt.height, display_family
    )
    overflow = await detect_overflow(html, fmt.width, fmt.height)
    issues.extend(overflow)

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

    png_bytes = await render_to_png(html, fmt.width, fmt.height)
    if not png_bytes:
        issues.append(
            "PNG render unavailable — the HTML was saved; re-render to regenerate the image"
        )
        passed = False
        score = min(score, 40)

    out_dir = os.path.join(settings.output_dir, task_id)
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{fmt_id}.png")
    html_path = os.path.join(out_dir, f"{fmt_id}.html")
    # The HTML is the source of truth — always persist it even if the PNG
    # render failed, so an edit is never lost to a render-service hiccup.
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    if png_bytes:
        with open(png_path, "wb") as fh:
            fh.write(png_bytes)

    # Reflect the rerender QC in the stored task result
    from datetime import datetime, timezone
    result = dict(task.result or {})
    platforms = dict(result.get("platforms") or {})
    platforms[fmt_id] = {
        **(platforms.get(fmt_id) or {}),
        "status": "verified" if passed else "needs_review",
        "quality_score": score,
        "quality_issues": issues,
        "html_path": html_path,
        "rerendered_at": datetime.now(timezone.utc).isoformat(),
    }
    result["platforms"] = platforms
    await repo.update_status(task_id=task_id, status=task.status, result=result)

    # Persist the edited HTML in the DB so an edit survives file consumption
    # and reloads — the file remains the delivery copy, the DB is durable.
    edited = dict(task.edited_html or {})
    edited[fmt_id] = html
    await repo.save_edited_html(task_id=task_id, edited_html=edited)

    return {
        "format": fmt_id,
        "pass": passed,
        "quality": {"score": score, "issues": issues, "critique": critique},
        "png_b64": base64.b64encode(png_bytes).decode("ascii") if png_bytes else "",
    }


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
        "tagline": slots.get("tagline", ""),
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
        "name": slots.get("footer_left", "") or request.name or template_id,
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
