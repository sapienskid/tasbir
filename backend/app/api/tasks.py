import base64
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.tasks import TaskRepository
from app.services.artifacts import (
    delete_task_output,
    list_output_files,
    resolve_output_file,
)
from app.services.formats import get_format_info, validate_platforms

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
            "created_at": t.created_at.isoformat() if t.created_at else None,
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
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.get("/{task_id}/files")
async def list_task_files(task_id: str, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    if not await repo.get_by_id(task_id):
        raise NotFoundError(f"Task {task_id} not found")
    return list_output_files(task_id)


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
    from app.agents.prompts.registry import load_prompt
    from app.config import get_settings
    from app.services.design_instruction import (
        build_google_fonts_link,
        inject_fonts_into_html,
        load_design_instruction,
        substitute_image_keys,
    )
    from app.services.dom_extractor import detect_overflow, render_to_png
    from app.services.sanitizer import sanitize_html
    from app.services.tokens import (
        DEFAULT_TOKEN_VALUES,
        inject_katex_into_html,
        inject_tokens_into_html,
        load_brand_design,
        load_tokens,
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
    tokens = load_tokens(settings.tokens_path) or dict(DEFAULT_TOKEN_VALUES)
    design_instruction = load_design_instruction(
        os.path.join(settings.design_system_dir, "design-instruction.yaml")
    )
    brand_design = load_brand_design(settings.brand_path)
    footer = brand_design["footer"]
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
            prompt_cfg = load_prompt("verifier")
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
        raise HTTPException(status_code=502, detail="PNG render unavailable")

    out_dir = os.path.join(settings.output_dir, task_id)
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{fmt_id}.png")
    html_path = os.path.join(out_dir, f"{fmt_id}.html")
    with open(png_path, "wb") as fh:
        fh.write(png_bytes)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)

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

    return {
        "format": fmt_id,
        "pass": passed,
        "quality": {"score": score, "issues": issues, "critique": critique},
        "png_b64": base64.b64encode(png_bytes).decode("ascii"),
    }


@router.post("/{task_id}/formats/{fmt_id}/template")
async def save_as_template(
    task_id: str,
    fmt_id: str,
    request: SaveTemplateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Promote a rendered/edited post into the template library.

    Reads the current [data-slot] content from the saved HTML, converts it to
    a Jinja2 template, validates it (render + overflow), and writes it to the
    library — as a new template (mode=new) or an update of the source template
    the post was built from (mode=update).
    """
    from app.services.artifacts import resolve_output_file
    from app.services.formats import get_format_info, validate_platforms
    from app.services.templates import (
        build_template_context,
        extract_slots,
        format_family,
        load_template_catalog,
        render_template_file,
        save_template,
        save_template_catalog,
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

    try:
        html_path = resolve_output_file(task_id, f"{fmt_id}.html")
    except FileNotFoundError:
        raise NotFoundError(f"No HTML for {fmt_id} — render it first")

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    platform = ((task.result or {}).get("platforms") or {}).get(fmt_id, {})
    source_template = platform.get("template_id") or ""
    family = format_family(fmt_id)

    if request.mode == "update":
        if not source_template:
            raise HTTPException(status_code=422, detail="This post was not built from a template")
        template_id = source_template
        catalog = load_template_catalog()
        entry = (catalog.get("templates") or {}).get(template_id)
        if not entry:
            raise HTTPException(
                status_code=422, detail=f"Source template {template_id!r} not found"
            )
        file = entry["file"]
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", (request.name or fmt_id).strip().lower())
        slug = slug.strip("-")
        if not slug:
            raise HTTPException(status_code=422, detail="Provide a template name")
        template_id = f"{family}-{slug}"
        file = f"{family}/{slug}.html"

    slots = extract_slots(html)
    if not slots:
        raise HTTPException(status_code=422, detail="No data-slot elements found in the HTML")

    template_html = slotize_html(html)

    # Validate before committing to the catalog: write the file, render it with
    # the extracted copy, and check overflow. Roll back the file on failure.
    saved_path = save_template(file, template_html)
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
        "black" if "data-ground=\"black\"" in html else "white",
        {"left": slots.get("footer_left", ""), "right": slots.get("footer_right", "")},
        fmt.width,
        fmt.height,
        False,
        seed=template_id,
    )
    from app.services.dom_extractor import detect_overflow

    try:
        rendered = render_template_file(file, context)
        overflow = await detect_overflow(rendered, fmt.width, fmt.height)
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Template render failed: {e}")
    if overflow:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Template overflows the canvas: " + "; ".join(overflow),
        )

    grounds = ["white", "black"] if "data-ground=\"black\"" in html else ["white"]
    catalog = load_template_catalog()
    catalog.setdefault("templates", {})
    catalog["templates"][template_id] = {
        "family": family,
        "grounds": grounds,
        "categories": [slots.get("kicker", "").upper()] if slots.get("kicker") else [],
        "hint_tags": [slots.get("kicker", "").lower()] if slots.get("kicker") else [],
        "weight": 1.0,
        "description": f"Promoted from task {task_id[:8]} ({fmt_id}).",
        "file": file,
    }
    save_template_catalog(catalog)

    return {"template_id": template_id, "mode": request.mode, "file": file}
