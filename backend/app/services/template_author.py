"""Template authoring agent — mockup image → validated Jinja2 template.

Chain:
  1. Template Vision   — mockup → structured layout spec JSON
  2. Template Author   — spec + design system → Jinja2 HTML
  3. Validation        — render sample copy → overflow + deterministic QC,
                         retrying the author with critique until clean
  4. Persist           — save a Template row under the design system

Shared by the standalone ``/templates/from-image`` job and the brand builder's
starter-template step.
"""

from __future__ import annotations

import json
import logging
import re

from app.models.design_system import DesignSystem
from app.services.agents import get_agent_config
from app.services.design_instruction import (
    format_design_instruction_block,
)
from app.services.design_systems import logo_data_uri
from app.services.llm import call_llm
from app.services.tokens import DEFAULT_TOKEN_VALUES
from app.services.vision import call_vision_llm

log = logging.getLogger(__name__)

MAX_AUTHOR_RETRIES = 3

FAMILY_DIMS: dict[str, tuple[int, int]] = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
    "landscape": (1200, 627),
}

SAMPLE_COPY = {
    "headline": "The quiet discipline of a well-set column of type",
    "subhead": "White space is the rhythm between ideas; a grid gives it a voice.",
    "body": "A grid sets order and a measure sets pace. Constrain the line, free "
    "the reader, and let the whitespace do its work.",
    "tagline": "No. 12 — On grids",
    "badge": None,
}


def extract_json(text: str) -> dict:
    text = text.strip()
    for candidate in (text, re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE).strip()):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not extract JSON from agent output: {text[:200]}")


def clean_html(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:html)?\s*\n?", "", raw, flags=re.MULTILINE | re.IGNORECASE)
    raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE)
    if "<!DOCTYPE" in raw.upper():
        return raw[raw.upper().index("<!DOCTYPE"):].strip()
    if "<html" in raw.lower():
        return raw[raw.lower().index("<html"):].strip()
    return raw.strip()


async def build_layout_spec(image_bytes: bytes, mime: str = "image/png") -> dict:
    """Template Vision: mockup → layout spec JSON."""
    prompt_cfg = await get_agent_config("template_vision")
    user_prompt = (
        "Analyze this social media post mockup and produce the layout specification.\n"
        f"Image mime: {mime}\n"
        'Return ONLY valid JSON per the schema in the system prompt.'
    )
    raw = await call_vision_llm(
        prompt_cfg.system_prompt,
        user_prompt,
        image_bytes,
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
        model=prompt_cfg.model,
        fallback_models=prompt_cfg.fallback_models,
    )
    return extract_json(raw)


def _design_context_block(ds: DesignSystem) -> str:
    """Design system rules the author must follow (tokens + instruction)."""
    tokens = dict(DEFAULT_TOKEN_VALUES)
    tokens.update(ds.tokens or {})
    di = ds.design_instruction or {}
    roles = ds.token_roles or {}
    lines = [
        "DESIGN SYSTEM (your template must use ONLY these):",
        "  Token variables:",
    ]
    for var, value in sorted(tokens.items()):
        if var.startswith("--color") or var.startswith("--font"):
            lines.append(f"    {var}: {value}")
    for var, role in sorted(roles.items()):
        if var not in tokens:
            continue
        lines.append(f"    {var} — role: {role}")
    if di:
        lines.append("\n" + format_design_instruction_block(di))
    return "\n".join(lines)


async def author_template_html(
    spec: dict,
    ds: DesignSystem,
    critique: str = "",
    ground_hint: str = "",
) -> str:
    """Template Author: spec + design system → Jinja2 HTML."""
    prompt_cfg = await get_agent_config("template_author")
    ground = ground_hint or spec.get("ground", "white")
    user_prompt = (
        f"LAYOUT SPEC (JSON):\n{json.dumps(spec, indent=2)}\n\n"
        f"EXPECTED GROUND: {ground}\n\n"
        f"{_design_context_block(ds)}\n\n"
        "Write the complete Jinja2 HTML template per the rules."
    )
    if critique:
        user_prompt += f"\n\nPREVIOUS VALIDATION FAILED — fix ALL of these:\n{critique}"
    raw = await call_llm(
        agent_role="template_author",
        system_prompt=prompt_cfg.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
    )
    return clean_html(raw)


async def validate_template_html(
    html: str,
    family: str,
    ds: DesignSystem,
    ground: str = "white",
) -> dict:
    """Render with sample copy + inject tokens/fonts, then overflow + QC.

    Returns {ok, issues, critique, rendered_html}. Render-service failure is a
    soft warning (the gallery re-validates on use) — only hard violations fail.
    """
    from app.agents.orchestrator.nodes.quality_check import _run_deterministic_checks
    from app.services.design_instruction import (
        build_google_fonts_link,
        inject_fonts_into_html,
        substitute_logo,
    )
    from app.services.dom_extractor import detect_overflow
    from app.services.templates import build_template_context, render_template_html

    width, height = FAMILY_DIMS.get(family, (1080, 1080))
    tokens = dict(DEFAULT_TOKEN_VALUES)
    tokens.update(ds.tokens or {})
    footer = ds.footer or {"left": "", "right": ""}
    logo = logo_data_uri(ds)

    context = build_template_context(
        dict(SAMPLE_COPY),
        "WRITING",
        ground if ground in ("white", "black") else "white",
        footer,
        width,
        height,
        False,
        seed="validate",
        family=family,
        logo=logo,
        di_config=ds.design_instruction or {},
    )
    try:
        rendered = render_template_html(html, context)
    except Exception as e:
        return {
            "ok": False,
            "issues": [f"Jinja2 render failed: {e}"],
            "critique": str(e),
            "rendered_html": "",
        }

    rendered = inject_fonts_into_html(
        rendered, build_google_fonts_link(tokens, ds.design_instruction or {})
    )
    rendered = substitute_logo(rendered, logo)
    try:
        from app.services.tokens import inject_tokens_into_html

        rendered = inject_tokens_into_html(rendered, tokens)
    except Exception:
        pass

    display_family = (
        tokens.get("--font-display") or DEFAULT_TOKEN_VALUES["--font-display"]
    ).split(",")[0].strip()
    issues = _run_deterministic_checks(
        rendered, footer, "WRITING", width, height, display_family
    )

    try:
        overflow = await detect_overflow(rendered, width, height)
        issues.extend(overflow)
    except Exception as e:
        log.warning("[template_author] overflow check skipped (render service): %s", e)

    critique = "Fix: " + "; ".join(issues) if issues else ""
    return {
        "ok": not issues,
        "issues": issues,
        "critique": critique,
        "rendered_html": rendered,
    }
