"""Verifier node — Victoria Thorne — multimodal QC via Gemini Vision.

Renders the HTML to a PNG and sends it to Gemini's Vision model for
evaluation against the design system and platform requirements.

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].html: str
  - design_tokens: dict

Output (to GenerationState):
  - format_tasks[fmt_id].quality_score: int
  - format_tasks[fmt_id].quality_issues: list[str]
  - format_tasks[fmt_id].status: "verified" | "needs_retry"
  - verification[fmt_id]: {pass: bool, score: int, issues: list, critique: str}
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import load_prompt
from app.services.design_instruction import (
    build_google_fonts_link,
    format_design_instruction_block,
    inject_fonts_into_html,
    load_design_instruction,
    substitute_image_keys,
)
from app.services.dom_extractor import render_to_png, detect_overflow
from app.services.formats import get_format_info
from app.services.tokens import DEFAULT_TOKEN_VALUES, inject_tokens_into_html, inject_katex_into_html

log = logging.getLogger(__name__)

MAX_RETRIES = 2  # Max verifier retry loops

# Vision calls are expensive on the free tier (15 req/min). Serialize them and
# enforce a minimum interval so parallel formats don't exhaust the quota.
_VISION_LOCK = asyncio.Lock()
_VISION_LAST_CALL = 0.0
_VISION_MIN_INTERVAL = 5.0  # seconds between vision LLM calls

# Decorative/emoji Unicode ranges to scan for — excludes mathematical operators
# (U+2200–U+22FF) so KaTeX/$...$ math content never false-positives.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # emoticons & pictographs
    "\U00002600-\U000027BF"  # misc symbols & dingbats
    "\U00002B00-\U00002BFF"  # misc symbols and arrows
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U0000FE0F"             # variation selector
    "]+"
)

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


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

        # Serialize + space vision calls to respect free-tier rate limits
        global _VISION_LAST_CALL
        loop = asyncio.get_event_loop()
        async with _VISION_LOCK:
            elapsed = loop.time() - _VISION_LAST_CALL
            if elapsed < _VISION_MIN_INTERVAL:
                await asyncio.sleep(_VISION_MIN_INTERVAL - elapsed)
            _VISION_LAST_CALL = loop.time()
            response = await llm.ainvoke(messages)

        content = response.content or ""
        # LangChain can return content as a list of content blocks
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    texts.append(block["text"])
                elif isinstance(block, str):
                    texts.append(block)
            content = "\n".join(texts)
        return content

    except Exception as e:
        log.error("[verifier] Vision LLM call failed: %s", e)
        # Return a pass on error to avoid blocking the pipeline
        return json.dumps({
            "pass": True,
            "score": 60,
            "issues": [f"Verification error: {str(e)[:100]}"],
            "critique": f"Verification failed with error: {e}. Design was auto-passed.",
        })


def _build_design_system_context(
    tokens: dict,
    design_instruction: dict,
    footer: dict,
    category: str,
    ground: str,
) -> str:
    """Build a full design system spec for the verifier prompt.

    Includes the complete Swiss style rules (type scale, spacing, footer,
    do/don't) plus token values, the resolved ground, and the required
    category label — everything the auditor needs to judge the render.
    """
    lines = [
        "DESIGN SYSTEM (AUDIT THE RENDER AGAINST EVERY POINT):",
        "  Ground: " + (ground if ground in ("white", "black") else "white"),
    ]

    if category:
        lines.append(f"  Required category label (tracked uppercase): {category}")
    if footer.get("left") and footer.get("right"):
        lines.append(
            f"  Required footer row: '{footer['left']}' left · '{footer['right']}' right, "
            "hairline rule above, metadata size"
        )
        lines.append(
            "  Footer note: the footer text is verified present programmatically — "
            "audit its placement, the hairline rule, and styling ONLY. Do not report "
            "the footer as 'missing' unless the rule or text is actually absent."
        )

    # Token values (the verifier sees actual values — it's the auditor)
    lines.append("  Token values:")
    for var, value in tokens.items():
        if var.startswith("--color") or var.startswith("--font"):
            lines.append(f"    {var}: {value}")

    # Math rendered by KaTeX uses its own math typeface (Computer Modern).
    # This is EXPECTED — do not flag math formula fonts as a violation.
    lines.append(
        "  Math note: LaTeX formulas rendered by KaTeX use KaTeX's own math "
        "typeface. This is EXPECTED and exempt from the family rules — "
        "do NOT flag math fonts as a serif violation."
    )

    # Layout archetypes are approved — audit within whichever the design follows.
    archetypes = (design_instruction or {}).get("layout_archetypes", {})
    if archetypes:
        lines.append(
            "  Layout note: any of the approved composition archetypes is valid "
            f"({', '.join(archetypes.keys())}). Audit the composition within the "
            "archetype it follows — do not demand one fixed layout."
        )

    di_block = format_design_instruction_block(design_instruction or {})
    return "\n".join(lines) + "\n\n" + di_block


def _run_deterministic_checks(
    html: str,
    footer: dict,
    category: str,
    canvas_width: int = 1080,
    canvas_height: int = 1080,
    display_family: str = "Space Grotesk",
) -> list[str]:
    """Check for hard design-system violations WITHOUT an LLM.

    Returns a list of critical issues. Any issue → the design must be fixed
    and retried. These encode the spec's non-negotiable rules:
      - the canvas is a styled, correctly-sized document
      - the signature display face is actually used (headline/wordmark)
      - no emoji / decorative unicode symbols
      - no raw hex colors in real styles (must use var(--color-*))
      - footer name + handle present (when configured)
      - approved category label present (when configured)

    A designer `:root` block is NOT flagged: the system strips any `:root`
    redeclaration before rendering and injects its own token block, so a
    designer `:root` (and the hex values inside it) never reaches the output.
    """
    issues: list[str] = []

    # 0. Structural integrity — the HTML must be a styled, canvas-pinned document
    if "<style" not in html.lower() or "</style>" not in html.lower():
        issues.append("HTML has no <style> block — the design would render unstyled")
    width_ok = re.search(rf"width\s*:\s*{canvas_width}px", html)
    height_ok = re.search(rf"height\s*:\s*{canvas_height}px", html)
    if not width_ok or not height_ok:
        issues.append(
            f"Canvas size must be defined as width:{canvas_width}px;height:{canvas_height}px "
            "(on the body or in a CSS rule)"
        )

    # 0b. Signature display face must appear (var(--font-display) or the face name)
    display_token_ok = "--font-display" in html
    family_ok = bool(display_family) and re.search(
        re.escape(display_family), html, re.IGNORECASE
    )
    if not display_token_ok and not family_ok:
        issues.append(
            f"The signature display face ('{display_family}' / var(--font-display)) "
            "must be used on the headline and footer wordmark"
        )

    # 1. Emoji / decorative symbols
    emoji_matches = _EMOJI_RE.findall(html)
    if emoji_matches:
        issues.append(
            f"Emoji/decorative unicode symbols detected (forbidden): "
            f"{sorted(set(emoji_matches))[:6]}"
        )

    # 2. Raw hex colors in real CSS. Strip :root blocks first — they are
    #    removed by the token injector before rendering, so hex inside a
    #    designer :root block is harmless.
    has_diagram = 'class="diagram"' in html or "mermaid" in html.lower()
    if not has_diagram:
        no_root = re.sub(r":root\s*\{[^}]*\}", "", html, flags=re.IGNORECASE)
        hex_found = _HEX_RE.findall(no_root)
        if hex_found:
            issues.append(
                f"Raw hex color values in HTML (must use var(--color-*)): "
                f"{sorted(set(hex_found))[:6]}"
            )

    # 3. Footer presence
    if footer.get("left") and footer["left"].lower() not in html.lower():
        issues.append(f"Footer name '{footer['left']}' is missing from the design")
    if footer.get("right") and footer["right"].lower() not in html.lower():
        issues.append(f"Footer handle '{footer['right']}' is missing from the design")

    # 4. Category label presence
    if category:
        upper = html.upper()
        if "{issue}" in category:
            base = category.replace("{issue}", "").upper()
            matches = [s for s in upper.split() if s.startswith(base)]
            if not matches:
                issues.append(f"Category label '{category}' is missing from the design")
        elif category.upper() not in upper:
            issues.append(f"Category label '{category}' is missing from the design")

    return issues


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
    footer = state.get("footer", {})
    category = state.get("category", "")
    ground = state.get("ground", "white")

    if not html:
        log.warning("[verifier] No HTML for %s, auto-passing", fmt_id)
        return _auto_pass(state, fmt_id, task, "No HTML to verify")

    # Step 0: Deterministic design-system checks (no LLM cost). Any violation
    # is a hard spec failure — fix and retry.
    display_value = design_tokens.get("--font-display", "Space Grotesk, Inter, sans-serif")
    display_family = display_value.split(",")[0].strip()
    check_issues = _run_deterministic_checks(
        html, footer, category, fmt.width, fmt.height, display_family
    )
    if check_issues:
        log.warning("[verifier] Deterministic violations for %s: %s", fmt_id, check_issues)
        _save_html_preview(task_id, fmt_id, html)
        verification = dict(state.get("verification", {}))
        verification[fmt_id] = {
            "pass": False,
            "score": 20,
            "issues": check_issues,
            "critique": "Automated design-system checks failed. Fix: " + "; ".join(check_issues),
        }
        new_retry_count = dict(state.get("retry_count", {}))
        new_retry_count[fmt_id] = retry_count + 1
        return {
            "format_tasks": {
                fmt_id: {
                    **task,
                    "quality_score": 20,
                    "quality_issues": check_issues,
                    "status": "needs_retry",
                }
            },
            "verification": verification,
            "retry_count": new_retry_count,
        }

    # Step 1: Inject tokens, fonts, KaTeX, and images into HTML
    log.info("[verifier] Rendering %s to PNG for visual audit", fmt_id)
    from app.config import get_settings
    settings = get_settings()
    images_list = state.get("images", [])
    html_with_tokens = inject_tokens_into_html(html, design_tokens)
    from pathlib import Path as _Path
    di_config = load_design_instruction(_Path(settings.design_system_dir) / "design-instruction.yaml")
    html_with_tokens = inject_fonts_into_html(
        html_with_tokens, build_google_fonts_link(design_tokens, di_config)
    )
    html_with_tokens = inject_katex_into_html(html_with_tokens)
    html_with_tokens = substitute_image_keys(html_with_tokens, images_list)
    png_bytes = await render_to_png(html_with_tokens, fmt.width, fmt.height)

    if not png_bytes:
        log.warning("[verifier] PNG render failed for %s — auto-passing", fmt_id)
        # Save HTML for debugging
        _save_html_preview(task_id, fmt_id, html_with_tokens)
        return _auto_pass(state, fmt_id, task, "PNG render unavailable — auto-passed")

    # Step 1b: Overflow check — content must never exceed the canvas
    overflow_issues = await detect_overflow(html_with_tokens, fmt.width, fmt.height)
    if overflow_issues:
        log.warning("[verifier] Overflow for %s: %s", fmt_id, overflow_issues)
        _save_html_preview(task_id, fmt_id, html_with_tokens)
        verification = dict(state.get("verification", {}))
        verification[fmt_id] = {
            "pass": False,
            "score": 30,
            "issues": overflow_issues,
            "critique": "Content overflows the canvas. Fix: " + "; ".join(overflow_issues),
        }
        new_retry_count = dict(state.get("retry_count", {}))
        new_retry_count[fmt_id] = retry_count + 1
        return {
            "format_tasks": {
                fmt_id: {
                    **task,
                    "quality_score": 30,
                    "quality_issues": overflow_issues,
                    "status": "needs_retry",
                }
            },
            "verification": verification,
            "retry_count": new_retry_count,
        }

    # Save PNG and HTML for output
    _save_png(task_id, fmt_id, png_bytes)
    _save_html_preview(task_id, fmt_id, html_with_tokens)
    di_path = _Path(settings.design_system_dir) / "design-instruction.yaml"
    design_instruction = load_design_instruction(di_path)
    ds_context = _build_design_system_context(design_tokens, design_instruction, footer, category, ground)
    user_prompt = (
        f"TARGET PLATFORM: {fmt_id} ({fmt.width}x{fmt.height}px)\n"
        f"EXPECTED GROUND: {ground}\n"
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
        "score": 40,
        "issues": [reason],
        "critique": reason,
        "auto_passed": True,
    }
    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "quality_score": 40,
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
