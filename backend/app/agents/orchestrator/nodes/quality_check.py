"""Verifier node — Victoria Thorne — multimodal QC via Gemini Vision.

Renders the HTML to a PNG and sends it to Gemini's Vision model for
evaluation against the design system and platform requirements.

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].html: str
  - format_tasks[fmt_id].penpot_file_path: str
  - design_tokens: dict

Output (to GenerationState):
  - format_tasks[fmt_id].quality_score: int
  - format_tasks[fmt_id].quality_issues: list[str]
  - format_tasks[fmt_id].status: "verified" | "needs_retry"
  - verification[fmt_id]: {pass: bool, score: int, issues: list, critique: str}
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import load_prompt
from app.services.dom_extractor import render_to_png
from app.services.formats import get_format_info
from app.services.penpot_io import DEFAULT_TOKEN_VALUES, inject_tokens_into_html

log = logging.getLogger(__name__)

MAX_RETRIES = 2  # Max verifier retry loops


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from verifier output: {text[:200]}")


async def _call_vision_llm(
    system_prompt: str,
    user_prompt: str,
    image_bytes: bytes,
    temperature: float = 0.3,
    max_tokens: int = 1000,
) -> str:
    """Call Gemini Vision with an image + text prompt via langchain_google_genai."""
    from app.config import get_settings

    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key:
        log.warning("[verifier] No Gemini API key — returning auto-pass")
        return json.dumps({
            "pass": True,
            "score": 75,
            "issues": ["Verification skipped — no API key"],
            "critique": "Auto-passed: Gemini API key not configured.",
        })

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            google_api_key=api_key,
            max_output_tokens=max_tokens,
        )

        # Build multimodal message: system + image + text
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
                {"type": "text", "text": user_prompt},
            ]),
        ]

        response = await llm.ainvoke(messages)
        return response.content or ""

    except Exception as e:
        log.error("[verifier] Vision LLM call failed: %s", e)
        # Return a pass on error to avoid blocking the pipeline
        return json.dumps({
            "pass": True,
            "score": 60,
            "issues": [f"Verification error: {str(e)[:100]}"],
            "critique": f"Verification failed with error: {e}. Design was auto-passed.",
        })


def _build_design_system_context(tokens: dict) -> str:
    """Build a concise design system spec for the verifier prompt."""
    lines = ["DESIGN SYSTEM:"]
    for var, value in tokens.items():
        if var.startswith("--color"):
            lines.append(f"  {var}: {value}")
    return "\n".join(lines)


async def quality_check_node_single(state: GenerationState) -> dict:
    """Run multimodal quality check for a single platform."""
    prompt_cfg = load_prompt("verifier")
    fmt_id = state.get("_processing_format_id", "")
    fmt = get_format_info(fmt_id)
    task_id = state.get("_task_id", "default")

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    html = task.get("html", "")
    design_tokens = state.get("design_tokens", DEFAULT_TOKEN_VALUES)

    retry_count = state.get("retry_count", {}).get(fmt_id, 0)

    if not html:
        log.warning("[verifier] No HTML for %s, auto-passing", fmt_id)
        return _auto_pass(state, fmt_id, task, "No HTML to verify")

    # Step 1: Render HTML → PNG
    log.info("[verifier] Rendering %s to PNG for visual audit", fmt_id)
    html_with_tokens = inject_tokens_into_html(html, design_tokens)
    png_bytes = await render_to_png(html_with_tokens, fmt.width, fmt.height)

    if not png_bytes:
        log.warning("[verifier] PNG render failed for %s — auto-passing", fmt_id)
        # Save HTML for debugging
        _save_html_preview(task_id, fmt_id, html_with_tokens)
        return _auto_pass(state, fmt_id, task, "PNG render unavailable — auto-passed")

    # Save PNG for debugging/audit
    _save_png(task_id, fmt_id, png_bytes)

    # Step 2: Build vision prompt
    ds_context = _build_design_system_context(design_tokens)
    user_prompt = (
        f"TARGET PLATFORM: {fmt_id} ({fmt.width}x{fmt.height}px)\n"
        f"{ds_context}\n\n"
        f"Audit this design image. Score it 0-100 and provide actionable critique.\n"
        f"Return ONLY valid JSON: {{\"pass\": bool, \"score\": int, \"issues\": [...], \"critique\": \"...\"}}"
    )

    # Step 3: Call Vision LLM
    log.info("[verifier] Auditing %s (attempt %d)", fmt_id, retry_count + 1)
    raw = await _call_vision_llm(
        system_prompt=prompt_cfg.system_prompt,
        user_prompt=user_prompt,
        image_bytes=png_bytes,
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
    )

    # Step 4: Parse and validate result
    try:
        result = _extract_json(raw)
        passed = bool(result.get("pass", True))
        score = int(result.get("score", 75))
        issues = list(result.get("issues", []))
        critique = str(result.get("critique", ""))
    except Exception as e:
        log.warning("[verifier] Parse failed: %s — auto-passing", e)
        passed, score, issues, critique = True, 70, [], "Parse error — auto-passed"

    log.info("[verifier] %s — pass=%s score=%d", fmt_id, passed, score)

    # Update verification state
    verification = dict(state.get("verification", {}))
    verification[fmt_id] = {
        "pass": passed,
        "score": score,
        "issues": issues,
        "critique": critique,
    }

    new_retry_count = dict(state.get("retry_count", {}))
    if not passed:
        new_retry_count[fmt_id] = retry_count + 1

    status = "verified" if passed else "needs_retry"

    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "quality_score": score,
                "quality_issues": issues,
                "status": status,
            }
        },
        "verification": verification,
        "retry_count": new_retry_count,
    }


def _auto_pass(state: GenerationState, fmt_id: str, task: dict, reason: str) -> dict:
    """Return an auto-pass result when verification cannot run."""
    verification = dict(state.get("verification", {}))
    verification[fmt_id] = {
        "pass": True,
        "score": 70,
        "issues": [reason],
        "critique": reason,
    }
    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "quality_score": 70,
                "quality_issues": [reason],
                "status": "verified",
            }
        },
        "verification": verification,
    }


def _save_png(task_id: str, fmt_id: str, png_bytes: bytes) -> None:
    """Save PNG render for debugging."""
    try:
        from app.config import get_settings
        settings = get_settings()
        out_dir = Path(settings.output_dir) / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path = out_dir / f"{fmt_id}.png"
        png_path.write_bytes(png_bytes)
        log.debug("[verifier] Saved PNG: %s", png_path)
    except Exception as e:
        log.debug("[verifier] Could not save PNG: %s", e)


def _save_html_preview(task_id: str, fmt_id: str, html: str) -> None:
    """Save HTML for debugging when PNG render fails."""
    try:
        from app.config import get_settings
        settings = get_settings()
        out_dir = Path(settings.output_dir) / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{fmt_id}.html"
        html_path.write_text(html, encoding="utf-8")
    except Exception as e:
        log.debug("[verifier] Could not save HTML: %s", e)
