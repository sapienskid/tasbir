"""Agent chat service — conversational design edits via Gemini.

Runs a single chat turn for a (task, format) thread. The assistant is the
designer persona in collaborative mode: it can see the current render
(vision) and may propose a full replacement HTML document, which the
frontend offers to the user for review before re-rendering.
"""

from __future__ import annotations

import json
import logging
import os
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator.nodes.quality_check import (
    _build_design_system_context,
    _call_vision_llm,
    _run_deterministic_checks,
)
from app.config import get_settings
from app.db.repositories.chat import ChatRepository
from app.services.agents import get_agent_config
from app.services.design_instruction import (
    build_google_fonts_link,
    inject_fonts_into_html,
    load_design_instruction,
)
from app.services.dom_extractor import detect_overflow, render_to_png
from app.services.formats import get_format_info, validate_platforms
from app.services.llm import call_llm
from app.services.sanitizer import sanitize_html
from app.services.tokens import (
    DEFAULT_TOKEN_VALUES,
    inject_katex_into_html,
    inject_tokens_into_html,
    load_tokens,
)

log = logging.getLogger(__name__)

_HTML_CAP = 80_000  # chars of current HTML shown to the model


async def _resolve_payload(db: AsyncSession, task: object) -> dict:
    """Design-system payload for the task — DB first, YAML fallback."""
    source_data = task.source_data or {}
    ds_id = source_data.get("design_system_id") or "default"

    try:
        from app.db.repositories.design_systems import DesignSystemRepository
        from app.services.design_systems import build_pipeline_payload

        if ds_id:
            ds = await DesignSystemRepository(db).get_by_id(ds_id)
            if ds is not None:
                return build_pipeline_payload(ds)
    except Exception as e:
        log.warning("[chat] Design-system load failed, using YAML fallback: %s", e)

    settings = get_settings()
    tokens = load_tokens(settings.tokens_path) or dict(DEFAULT_TOKEN_VALUES)
    di = load_design_instruction(
        os.path.join(settings.design_system_dir, "design-instruction.yaml")
    )
    brand = {}
    footer = {"left": "", "right": ""}
    try:
        from app.services.tokens import load_brand_design
        brand = load_brand_design(settings.brand_path)
        footer = brand.get("footer") or footer
    except Exception:
        pass
    return {
        "design_system_id": ds_id or "default",
        "design_tokens": tokens,
        "design_instruction": di,
        "footer": footer,
        "categories": [],
    }


async def _current_html(task: object, fmt_id: str) -> str | None:
    """Read the last saved render for a format ('' when none)."""
    try:
        from app.services.artifacts import resolve_output_file
        path = resolve_output_file(task.id, f"{fmt_id}.html")
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


async def _precheck_html(
    html: str, payload: dict, fmt, footer: dict, category: str, ground: str
) -> dict:
    """Sanitize + inject + run deterministic/overflow checks on proposed HTML.

    Returns ``{ok: bool, issues: [...]}``. Soft gate — the proposal is still
    returned to the user, but the issues are surfaced for review.
    """
    tokens = payload.get("design_tokens") or dict(DEFAULT_TOKEN_VALUES)
    di = payload.get("design_instruction") or {}

    clean = sanitize_html(html, mode="preserve_system")
    if "cdn.jsdelivr.net/npm/katex" not in clean:
        clean = inject_katex_into_html(clean)
    clean = inject_tokens_into_html(clean, tokens)
    clean = inject_fonts_into_html(clean, build_google_fonts_link(tokens, di))

    display_value = tokens.get("--font-display", "Space Grotesk, Inter, sans-serif")
    display_family = display_value.split(",")[0].strip()
    issues = _run_deterministic_checks(
        clean, footer, category, fmt.width, fmt.height, display_family
    )
    overflow = await detect_overflow(clean, fmt.width, fmt.height)
    issues.extend(overflow)
    return {"ok": not issues, "issues": issues}


def _parse_reply(raw: str) -> dict:
    """Parse the assistant's JSON reply; fall back to prose on malformed JSON."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"reply": raw, "changed": False, "html": None}


async def run_chat_turn(
    db: AsyncSession,
    task: object,
    fmt_id: str,
    message: str,
    html: str | None = None,
) -> dict:
    """Run one chat turn: persist user msg, call the assistant, persist reply."""
    validated = validate_platforms([fmt_id])
    fmt_id = validated[0]
    fmt = get_format_info(fmt_id)

    payload = await _resolve_payload(db, task)
    tokens = payload.get("design_tokens") or dict(DEFAULT_TOKEN_VALUES)
    footer = payload.get("footer") or {"left": "", "right": ""}
    design_instruction = payload.get("design_instruction") or {}

    result = task.result or {}
    brief = result.get("strategic_brief") or {}
    source_data = task.source_data or {}
    category = source_data.get("category") or brief.get("category") or ""
    ground = brief.get("ground", "white")
    if ground not in ("white", "black"):
        ground = "white"

    repo = ChatRepository(db)
    thread = await repo.get_or_create_thread(task.id, fmt_id)
    await repo.add_message(thread.id, "user", message)

    # The editor's live draft is already token-injected; fall back to the
    # last saved render otherwise.
    current = (html or "").strip() or (await _current_html(task, fmt_id)) or ""

    ds_context = _build_design_system_context(
        tokens, design_instruction, footer, category, ground
    )
    prompt_cfg = await get_agent_config("editor_chat")

    html_excerpt = current
    if len(html_excerpt) > _HTML_CAP:
        html_excerpt = html_excerpt[:_HTML_CAP] + "\n<!-- …truncated… -->"
    user_prompt = (
        f"TARGET PLATFORM: {fmt_id} ({fmt.width}x{fmt.height}px)\n"
        f"EXPECTED GROUND: {ground}\n"
        f"CURRENT HTML DOCUMENT (edit this if you propose changes):\n"
        f"{html_excerpt}\n\n"
        f"DESIGN SYSTEM CONTEXT:\n{ds_context}\n\n"
        f"USER REQUEST: {message}\n\n"
        "Reply conversationally. If the user wants a change, return ONLY valid "
        'JSON: {"reply": "<your message>", "changed": bool, '
        '"html": "<complete replacement HTML document or null>"}. '
        "The html must keep the canvas-pinned width/height, use var(--color-*) "
        "and var(--font-*) exclusively (no raw hex, no emoji), and include a "
        "<style> block. Return html:null when only a conversational reply is "
        "needed. If you return json, reply MUST be the prose inside that JSON."
    )

    # Vision: render the current state so the assistant sees the design.
    png_bytes = None
    if current:
        try:
            png_bytes = await render_to_png(current, fmt.width, fmt.height)
        except Exception as e:
            log.warning("[chat] render_to_png failed: %s", e)
            png_bytes = None

    try:
        if png_bytes:
            raw = await _call_vision_llm(
                system_prompt=prompt_cfg.system_prompt,
                user_prompt=user_prompt,
                image_bytes=png_bytes,
                temperature=prompt_cfg.temperature,
                max_tokens=prompt_cfg.max_tokens,
            )
        else:
            raw = await call_llm(
                agent_role="editor_chat",
                system_prompt=prompt_cfg.system_prompt,
                user_prompt=user_prompt,
                temperature=prompt_cfg.temperature,
                max_tokens=prompt_cfg.max_tokens,
            )
    except Exception as e:
        await repo.add_message(
            thread.id,
            "assistant",
            f"I hit an error talking to the model: {e}",
        )
        return {"reply": f"Error: {e}", "html": None, "qc": None, "thread_id": thread.id}

    try:
        parsed = _parse_reply(raw)
    except Exception:
        parsed = {"reply": raw, "changed": False, "html": None}

    reply = str(parsed.get("reply") or raw).strip()
    proposed = parsed.get("html") or None
    if isinstance(proposed, str):
        proposed = proposed.strip() or None

    qc = None
    if proposed and len(proposed) > 50:
        try:
            qc = await _precheck_html(proposed, payload, fmt, footer, category, ground)
        except Exception as e:
            log.warning("[chat] precheck failed: %s", e)
            qc = {"ok": False, "issues": [f"Pre-check error: {e}"]}
    elif proposed:
        proposed = None

    await repo.add_message(thread.id, "assistant", reply, html=proposed)

    return {
        "reply": reply,
        "html": proposed,
        "qc": qc,
        "thread_id": thread.id,
    }
