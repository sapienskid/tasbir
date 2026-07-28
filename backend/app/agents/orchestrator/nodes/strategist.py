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
from app.agents.prompts.registry import load_prompt
from app.services.llm import call_llm

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------


class StrategicBrief(BaseModel):
    angle: str
    audience: str
    tone: str
    visual_direction: str
    platform_notes: dict[str, str] = {}

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v: str) -> str:
        valid = {"professional", "warm", "energetic", "minimal", "luxury", "bold", "editorial"}
        # Accept any tone but normalize it
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


async def strategist_node(state: GenerationState) -> dict:
    """Analyze content and produce a structured strategic brief."""
    prompt_cfg = load_prompt("strategist")
    content = state.get("content", "")
    title = state.get("title", "")
    platforms = state.get("platforms", [])

    # Build a lean user prompt — only what the agent needs
    user_prompt = (
        f"TITLE: {title}\n\n"
        f"TARGET PLATFORMS: {', '.join(platforms)}\n\n"
        f"CONTENT:\n{content[:3000]}"  # Truncate to avoid token flood
    )

    log.info("[strategist] Analyzing content for %d platform(s)", len(platforms))

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
        return {"strategic_brief": brief.model_dump()}

    except Exception as e:
        log.error("[strategist] Failed: %s", e, exc_info=True)
        # Return a minimal fallback brief so the pipeline can continue
        fallback = StrategicBrief(
            angle=f"Key insights from: {title}",
            audience="General audience interested in this topic",
            tone="professional",
            visual_direction="clean editorial",
            platform_notes={p: f"Optimized for {p}" for p in platforms},
        )
        return {"strategic_brief": fallback.model_dump()}
