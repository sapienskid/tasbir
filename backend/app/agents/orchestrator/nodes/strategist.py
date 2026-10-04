"""Strategist node — Aura Vance — analyzes content → structured brief.

Produces a strategic brief (angle, audience, tone, visual_direction,
platform_notes) as validated JSON. The LLM never sees design tokens or
brand colors — it only sets strategic direction.

Input (from GenerationState):
  - content: str (full article/blog text)
  - title: str
  - platforms: list[str]

Output (to GenerationState):
  - strategic_brief: dict (validated StrategicBrief)
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, field_validator

from app.agents.orchestrator.state import GenerationState
from app.services.agents import get_agent_config
from app.services.llm import call_llm
from app.services.tokens import category_matches, resolve_ground

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------


class StrategicBrief(BaseModel):
    angle: str
    audience: str
    tone: str
    visual_direction: str
    category: str = ""
    ground: str = ""
    template_hint: str = ""
    # Set when the intake-router decision pack flags the input as needing a
    # human look (ambiguous / sensitive / self-contradictory). Advisory —
    # the pipeline still runs; the Studio surfaces the flag.
    needs_review: bool = False
    platform_notes: dict[str, str] = {}
    # Key themes + searchable keywords (~150 words, no colors/emoji). Feeds the
    # media-plan director so photo searches + illustration subjects match the
    # actual content.
    content_summary: str = ""

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v: str) -> str:
        # Accept any tone but normalize it.
        return v.lower().strip() if v else "professional"


def _extract_json(text: str) -> dict:
    """Extract the first valid JSON object from LLM output."""
    # Direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON object with regex
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM output: {text[:200]}")


def _intake_noul(answers: dict, qid: str) -> float:
    """Noul probability for a question id (0.0 when absent — fail-open)."""
    try:
        return float((answers.get(qid) or {}).get("noul", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _intake_policy(answers: dict, thresholds: dict) -> dict:
    """Turn intake-router answers + probabilities into actions.

    - ``block``: safety_flag at/above ``safety_block`` → refuse the task
      (hard fail with a clear message, never a silent fallback).
    - ``needs_review``: needs_human at/above 0.5 → advisory flag on the brief.
    Empty answers (providers down) yield no action — fail-open.
    """
    if not answers:
        return {"safety": 0.0, "needs_human": 0.0, "block": False, "needs_review": False}
    safety = _intake_noul(answers, "safety_flag")
    needs_human = _intake_noul(answers, "needs_human")
    try:
        block_at = float(thresholds.get("safety_block", 0.8))
    except (TypeError, ValueError):
        block_at = 0.8
    return {
        "safety": safety,
        "needs_human": needs_human,
        "block": safety >= block_at,
        "needs_review": needs_human >= 0.5,
    }


async def _fetch_intake_answers(state: GenerationState, title: str, content: str) -> tuple[dict, dict]:
    """Run the intake-router pack once (fail-open → ({}, {}) on any failure)."""
    from app.services.decision_packs import get_pack
    from app.services.decisions import decide, providers_configured

    if not providers_configured():
        return {}, {}
    try:
        categories = state.get("categories", [])
        approved = [str(c.get("name", "")) for c in (categories or [])]
        d_res = await decide(
            "intake-router",
            {
                "title": title,
                "excerpt": str(state.get("excerpt", ""))[:500],
                "content": str(content)[:1500],
                "approved_categories": approved,
            },
            metadata={"agent": "strategist"},
        )
        answers = d_res.get("answers", {})
        info = {
            "provider": d_res.get("provider", ""),
            "model": d_res.get("model", ""),
            "pack_version": d_res.get("pack_version", 1),
            **_intake_policy(answers, get_pack("intake-router").get("thresholds", {})),
        }
        return answers, info
    except Exception as e:  # noqa: BLE001
        log.warning("[strategist] intake-router skipped: %s", e)
        return {}, {}


def _fallback_summary(title: str, tags: list[str]) -> str:
    """Deterministic content summary for the fallback brief (no LLM)."""
    parts = [title.strip()] if title.strip() else []
    parts += [t.strip() for t in tags if t.strip()]
    return ", ".join(parts)[:300] or "General topic summary"


def _ds_default_ground(state: GenerationState) -> str:
    """The design language's preferred ground (style.default_ground)."""
    di = state.get("design_instruction") or {}
    default = (di.get("style") or {}).get("default_ground") or "white"
    return default if default in ("white", "black") else "white"


async def strategist_node(state: GenerationState) -> dict:
    """Analyze content and produce a structured strategic brief."""
    # Retry-from-failure: the brief is already present from the failed run.
    if state.get("strategic_brief"):
        return {}
    prompt_cfg = await get_agent_config("strategist")
    content = state.get("content", "")
    title = state.get("title", "")
    # "auto" is resolved by the planner downstream — keep only concrete platforms.
    platforms = [p for p in state.get("platforms", []) if p != "auto"]
    categories = state.get("categories", [])

    # Build brand + campaign context
    brand_info = state.get("brand_info", {})
    campaign = state.get("campaign", {})
    brand_block = ""
    if brand_info.get("name"):
        brand_block = (
            f"BRAND: {brand_info.get('name', '')}\n"
            f"TAGLINE: {brand_info.get('tagline', '')}\n"
            f"MISSION: {brand_info.get('mission', '')}\n"
            f"STORY: {brand_info.get('story', '')}\n"
        )

    campaign_block = ""
    if campaign:
        label = campaign.get("label", "")
        tone = campaign.get("tone", "")
        ground = campaign.get("ground", "")
        language = campaign.get("language", "")
        campaign_block = (
            f"CAMPAIGN: {label}\n"
            f"TONE: {tone}\n"
            f"GROUND: {ground}\n"
            f"LANGUAGE: {language}\n"
        )

    # Approved category taxonomy (exact strings the designer must use)
    categories_block = ""
    if categories:
        cat_lines = []
        for cat in categories:
            name = cat.get("name", "")
            desc = cat.get("description", "")
            ground = cat.get("ground", "")
            ground_note = f" [ground: {ground}]" if ground else ""
            cat_lines.append(f"  {name} — {desc}{ground_note}")
        categories_block = "APPROVED CATEGORY LABELS (choose exactly one):\n" + "\n".join(cat_lines) + "\n"

    # Template library — the strategist can hint at a composition style.
    template_catalog = {
        t.get("id", ""): t
        for t in (state.get("ds_templates") or [])
        if t.get("id")
    }
    template_block = ""
    if template_catalog:
        tpl_lines = []
        for tid, e in template_catalog.items():
            fam = e.get("family", "?")
            desc = e.get("description", "")
            tpl_lines.append(f"  {tid} ({fam}) — {desc}")
        template_block = (
            "AVAILABLE TEMPLATES (choose the closest id for the visual direction, "
            "or leave template_hint empty for free-form):\n"
            + "\n".join(tpl_lines)
            + "\n"
        )

    # Tags & excerpt
    tags_str = ", ".join(state.get("tags", []))
    excerpt_str = state.get("excerpt", "")

    user_prompt = (
        f"TITLE: {title}\n\n"
        f"{brand_block}\n"
        f"{campaign_block}\n"
        f"{categories_block}\n"
        f"{template_block}\n"
        f"TARGET PLATFORMS: {', '.join(platforms)}\n"
        f"TAGS: {tags_str}\n"
        f"EXCERPT: {excerpt_str}\n\n"
        f"CONTENT:\n{content[:3000]}"
    )

    log.info("[strategist] Analyzing content for %d platform(s)", len(platforms))

    # Category override (API or brand overrides) wins — no LLM needed for it
    override_category = str(state.get("overrides", {}).get("category") or state.get("category") or "").strip()

    # Decision intake gate — runs BEFORE the LLM so an unsafe input never
    # spends generation budget. Fail-open on provider errors (no answers →
    # no action); hard block only on a real safety verdict. The category vote
    # below only applies when the LLM missed the taxonomy and never
    # overrides an explicit user/brand category.
    intake_answers, decision_info = await _fetch_intake_answers(state, title, content)
    if decision_info.get("block"):
        msg = (
            "intake safety gate blocked this content "
            f"(safety={decision_info.get('safety', 0):.2f} via {decision_info.get('provider', '?')})"
        )
        log.warning("[strategist] %s", msg)
        task_id = state.get("_task_id", "")
        if task_id:
            from app.services.audit import record_audit

            await record_audit(task_id, "strategist",
                               decision={"blocked": True, "intake_router": decision_info})
        raise RuntimeError(msg)

    try:
        raw = await call_llm(
            agent_role="strategist",
            system_prompt=prompt_cfg.system_prompt,
            user_prompt=user_prompt,
            temperature=prompt_cfg.temperature,
            max_tokens=prompt_cfg.max_tokens,
        )

        data = _extract_json(raw)

        # Ensure platform_notes has entries for all requested platforms
        if "platform_notes" not in data:
            data["platform_notes"] = {}
        for platform in platforms:
            if platform not in data["platform_notes"]:
                data["platform_notes"][platform] = f"Optimized for {platform}"

        brief = StrategicBrief(**data)
        log.info("[strategist] Brief produced — angle: %s", brief.angle[:60])

        # Resolve category: override > LLM > WRITING fallback
        category = override_category.upper() if override_category else (brief.category or "").upper().strip()
        if not category_matches(category, categories):
            log.warning("[strategist] Category '%s' not approved — falling back to WRITING", category)
            category = "WRITING"

        # Second vote from the intake-router pack (already fetched above —
        # no extra call). Adopts the vote only when the LLM missed the
        # taxonomy; records the human-review flag either way.
        if category == "WRITING" and not override_category and intake_answers:
            cat_ans = intake_answers.get("category", {})
            voted = str(cat_ans.get("choice", "") or "").upper().strip()
            decision_info = {
                **decision_info,
                "voted_category": voted,
                "confidence": cat_ans.get("confidence"),
            }
            if voted and voted != "OTHER" and category_matches(voted, categories):
                log.info("[strategist] intake-router voted %s (conf %s) — adopting", voted, cat_ans.get("confidence"))
                category = voted
                brief.category = voted
        if decision_info.get("needs_review"):
            brief.needs_review = True

        ground = resolve_ground(
            campaign,
            category,
            categories,
            default=_ds_default_ground(state),
        )
        brief.category = category
        brief.ground = ground

        task_id = state.get("_task_id", "")
        if task_id:
            from app.services.audit import record_audit

            await record_audit(
                task_id,
                "strategist",
                decision={
                    "category": category,
                    "ground": ground,
                    "template_hint": brief.template_hint or "",
                    **({"intake_router": decision_info} if decision_info else {}),
                },
                critique=brief.angle,
            )

        return {
            "strategic_brief": brief.model_dump(),
            "category": category,
            "ground": ground,
        }

    except Exception as e:
        log.error("[strategist] Failed: %s", e, exc_info=True)
        # Return a minimal fallback brief so the pipeline can continue
        category = override_category.upper() if override_category else "WRITING"
        if not category_matches(category, categories):
            category = "WRITING"
        ground = resolve_ground(
            campaign,
            category,
            categories,
            default=_ds_default_ground(state),
        )
        fallback = StrategicBrief(
            angle=f"Key insights from: {title}",
            audience="General audience interested in this topic",
            tone="professional",
            visual_direction="clean editorial",
            category=category,
            ground=ground,
            platform_notes={p: f"Optimized for {p}" for p in platforms},
            content_summary=_fallback_summary(title, state.get("tags", [])),
        )
        return {
            "strategic_brief": fallback.model_dump(),
            "category": category,
            "ground": ground,
        }
