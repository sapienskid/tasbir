"""Playground — test design token rendering without LLM calls.

Endpoints:
  POST   /playground/render-preview   — render single template (HTML or PNG)
  POST   /playground/test-suite       — run full test suite (all tokens × templates)
  GET    /playground/test-suite/{id}  — get test suite results
  GET    /playground/test-suite/{id}/files/{token_name}/{template_name}.{ext}
                                       — serve saved HTML/PNG from a run
  GET    /playground/token-list        — list available token sets
  GET    /playground/templates         — list available templates
"""

import json
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.agents.orchestrator.nodes.designer import _inject_theme
from app.services.formats import get_format_info

router = APIRouter(tags=["playground"])

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "test_templates"
RESULTS_DIR = Path(__file__).resolve().parents[2] / "playground-results"


class RenderPreviewRequest(BaseModel):
    token_id: str | None = None
    template_name: str = "full-composite"
    format_id: str = "instagram-square"
    brand: dict = {}
    render: bool = False


class TestSuiteRequest(BaseModel):
    format_id: str = "instagram-square"
    token_ids: list[str] | None = None
    template_names: list[str] | None = None


# ── Helper: render a single template with tokens ──────────────────────

async def _render_one(
    template_name: str,
    format_id: str,
    tokens: dict,
    brand: dict | None = None,
) -> tuple[str, bytes | None]:
    """Returns (html_string, png_bytes_or_None)."""
    template_path = TEMPLATES_DIR / f"{template_name}.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    fmt_info = await get_format_info(format_id)
    body_partial = template_path.read_text(encoding="utf-8")
    body_html = (
        f'<div style="width: {fmt_info.width}px; height: {fmt_info.height}px; overflow: hidden;">\n'
        f'{body_partial}\n'
        f"</div>"
    )

    from app.agents.orchestrator.nodes.designer import _extract_html
    html = _extract_html(body_html)
    html = _inject_theme(html, tokens, brand=brand or None)

    from app.services.cleanup import clean_html
    html = clean_html(html)

    from app.services.renderer import render_html
    png = await render_html(
        html,
        format_id=format_id,
        width=fmt_info.width,
        height=fmt_info.height,
    )

    return html, png


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/token-list")
async def list_tokens():
    from sqlalchemy import select
    from app.models.tokens import DesignToken
    from app.db.session import get_shared_session_factory
    pool = await get_shared_session_factory()
    async with pool() as session:
        result = await session.execute(select(DesignToken).order_by(DesignToken.name))
        tokens = result.scalars().all()
        return [
            {"id": str(t.id), "name": t.name, "version": t.version, "source": t.source}
            for t in tokens
        ]


@router.get("/templates")
async def list_templates():
    if not TEMPLATES_DIR.exists():
        return {"templates": []}
    templates = sorted(p.stem for p in TEMPLATES_DIR.glob("*.html"))
    return {"templates": templates}


@router.post("/render-preview")
async def render_preview(req: RenderPreviewRequest):
    tokens = {}
    if req.token_id:
        from uuid import UUID
        from sqlalchemy import select
        from app.models.tokens import DesignToken
        from app.db.session import get_shared_session_factory
        pool = await get_shared_session_factory()
        async with pool() as session:
            result = await session.execute(
                select(DesignToken).where(DesignToken.id == UUID(req.token_id))
            )
            dt = result.scalar_one_or_none()
            if dt and dt.data:
                tokens = dt.data

    html, png = await _render_one(req.template_name, req.format_id, tokens, req.brand or None)

    if req.render:
        if png is None:
            raise HTTPException(status_code=502, detail="Rendering failed")
        return Response(content=png, media_type="image/png")

    return HTMLResponse(html)


@router.post("/test-suite")
async def run_test_suite(req: TestSuiteRequest):
    """Run full test suite: all token sets × all templates.

    Saves every combination as HTML + PNG to playground-results/{run_id}/.
    Returns a structured report with links to each result.
    """
    from sqlalchemy import select
    from app.models.tokens import DesignToken
    from app.db.session import get_shared_session_factory
    pool = await get_shared_session_factory()

    # Load tokens
    async with pool() as session:
        result = await session.execute(select(DesignToken).order_by(DesignToken.name))
        all_tokens_db = result.scalars().all()

    token_sets = []
    if req.token_ids:
        id_set = set(req.token_ids)
        for t in all_tokens_db:
            if str(t.id) in id_set:
                token_sets.append({"id": str(t.id), "name": t.name, "data": t.data})
    else:
        for t in all_tokens_db:
            token_sets.append({"id": str(t.id), "name": t.name, "data": t.data})
    # Always include "no tokens" (defaults) test case
    token_sets.append({"id": "", "name": "defaults-only", "data": {}})

    # Load templates
    all_templates = sorted(p.stem for p in TEMPLATES_DIR.glob("*.html"))
    templates = [t for t in all_templates if not req.template_names or t in req.template_names]

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(token_sets) * len(templates)
    completed = 0

    for ts in token_sets:
        token_dir = run_dir / _safe_name(ts["name"])
        token_dir.mkdir(exist_ok=True)

        for tmpl in templates:
            result_entry = {
                "token_name": ts["name"],
                "template": tmpl,
                "format": req.format_id,
                "html_size": 0,
                "png_size": 0,
                "success": False,
                "error": None,
                "html_url": None,
                "png_url": None,
            }

            try:
                html, png = await _render_one(tmpl, req.format_id, ts["data"])

                # Save HTML
                html_path = token_dir / f"{tmpl}.html"
                html_path.write_text(html, encoding="utf-8")
                result_entry["html_size"] = html_path.stat().st_size
                result_entry["html_url"] = f"/playground/test-suite/{run_id}/files/{_safe_name(ts['name'])}/{tmpl}.html"

                # Save PNG
                if png:
                    png_path = token_dir / f"{tmpl}.png"
                    png_path.write_bytes(png)
                    result_entry["png_size"] = png_path.stat().st_size
                    result_entry["png_url"] = f"/playground/test-suite/{run_id}/files/{_safe_name(ts['name'])}/{tmpl}.png"
                    result_entry["success"] = True
                else:
                    result_entry["error"] = "Render returned None"

            except Exception as e:
                result_entry["error"] = str(e)

            results.append(result_entry)
            completed += 1

    report = {
        "run_id": run_id,
        "format": req.format_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_sets": len(token_sets),
        "templates": len(templates),
        "total": total,
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "results": results,
    }

    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return report


@router.get("/test-suite/{run_id}")
async def get_test_suite(run_id: str):
    """Get the report for a completed test suite run."""
    report_path = RESULTS_DIR / run_id / "report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report


@router.get("/test-suite/runs")
async def list_test_suite_runs():
    """List all completed test suite runs."""
    if not RESULTS_DIR.exists():
        return {"runs": []}
    runs = []
    for d in sorted(RESULTS_DIR.iterdir(), reverse=True):
        report_path = d / "report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            runs.append({
                "run_id": d.name,
                "timestamp": report.get("timestamp", ""),
                "format": report.get("format", ""),
                "total": report.get("total", 0),
                "successful": report.get("successful", 0),
                "failed": report.get("failed", 0),
            })
    return {"runs": runs}


@router.get("/test-suite/{run_id}/files/{token_name}/{file_name}")
async def serve_test_file(run_id: str, token_name: str, file_name: str):
    """Serve saved HTML/PNG files from a test suite run."""
    file_path = RESULTS_DIR / run_id / _safe_name(token_name) / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if file_name.endswith(".html"):
        return HTMLResponse(file_path.read_text(encoding="utf-8"))
    elif file_name.endswith(".png"):
        return Response(content=file_path.read_bytes(), media_type="image/png")
    raise HTTPException(status_code=400, detail="Unsupported file type")


@router.get("/tokens/{token_id}")
async def token_playground(token_id: str):
    """Standalone HTML page showing all design token specimens."""
    from uuid import UUID
    from sqlalchemy import select
    from app.models.tokens import DesignToken
    from app.db.session import get_shared_session_factory
    pool = await get_shared_session_factory()
    async with pool() as session:
        result = await session.execute(
            select(DesignToken).where(DesignToken.id == UUID(token_id))
        )
        dt = result.scalar_one_or_none()
        if not dt or not dt.data:
            raise HTTPException(status_code=404, detail="Token set not found")
        tokens = dt.data

    from app.agents.orchestrator.nodes.designer import _inject_theme
    from app.services.token_exchange import _flatten

    flat = _flatten(tokens)

    color_swatches = ""
    for path, val in sorted(flat.items()):
        if "color" in path.lower():
            name = path.replace("/", ".")
            color_swatches += (
                f'<div class="flex items-center gap-3 p-3 rounded-lg bg-elevated">'
                f'<div class="w-10 h-10 rounded-lg" style="background:{val}"></div>'
                f'<div><div class="text-xs text-text font-medium">{name}</div>'
                f'<div class="text-[11px] text-text-secondary">{val}</div></div></div>'
            )

    typography_samples = ""
    font_keys = [k for k in flat if "fontfamily" in k.lower() or "family" in k.lower()]
    for k in font_keys:
        name = k.split("/")[-1]
        font_val = flat[k]
        typography_samples += (
            f'<div class="p-4 rounded-lg bg-elevated">'
            f'<div class="text-[11px] text-text-secondary mb-1">font-{name} ({font_val})</div>'
            f'<p class="text-lg text-text" style="font-family:{font_val}">'
            f"The quick brown fox jumps over the lazy dog</p></div>"
        )

    body = f"""
    <div class="max-w-3xl mx-auto p-8 space-y-8">
        <div>
            <h1 class="text-2xl font-serif text-text">Design Tokens</h1>
            <p class="text-sm text-text-secondary">{dt.name} v{dt.version}</p>
        </div>
        <div>
            <h2 class="text-sm font-medium text-text mb-3">Colors</h2>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">{color_swatches}</div>
        </div>
        <div>
            <h2 class="text-sm font-medium text-text mb-3">Typography</h2>
            <div class="space-y-3">{typography_samples}</div>
        </div>
        <div>
            <h2 class="text-sm font-medium text-text mb-3">Spacing</h2>
            <div class="space-y-2">
                {''.join(
                    f'<div class="flex items-center gap-3"><span class="text-xs text-text-secondary w-20">{k.split("/")[-1]}</span><div class="h-4 rounded" style="width:{v};background:var(--color-accent, #CD5B7D)"></div></div>'
                    for k, v in sorted(flat.items()) if "spacing" in k.lower() or "padding" in k.lower() or "gap" in k.lower() or "scale" in k.lower()
                )}
            </div>
        </div>
    </div>
    """

    tokens_for_inject = dt.data
    full_html = _inject_theme(
        f"<!DOCTYPE html><html><head></head><body>{body}</body></html>",
        tokens_for_inject,
    )

    return HTMLResponse(full_html)


# ── Helpers ───────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Make a string safe for use as a directory/filename."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).lower() or "unnamed"
