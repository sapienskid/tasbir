"""YAML prompt loader — reads agent prompts from config/prompts/*.yaml.

Each YAML file has:
  persona: "Agent Name"
  role: "Agent Role"
  system_prompt: |
    Full system prompt text...
  temperature: 0.7
  max_tokens: 2000
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Resolve config dir relative to this file (backend/app/agents/prompts/ → backend/config/prompts/)
_THIS_DIR = Path(__file__).parent
_PROMPTS_DIR = _THIS_DIR.parent.parent.parent / "config" / "prompts"
if not _PROMPTS_DIR.exists():
    _PROMPTS_DIR = _THIS_DIR.parent.parent.parent.parent / "config" / "prompts"



@dataclass
class PromptConfig:
    persona: str
    role: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2000


@lru_cache(maxsize=32)
def load_prompt(agent_name: str) -> PromptConfig:
    """Load a YAML prompt config by agent name.

    Looks in backend/config/prompts/{agent_name}.yaml.
    Falls back to inline defaults if the file is missing.
    """
    import yaml

    yaml_path = _PROMPTS_DIR / f"{agent_name}.yaml"

    if not yaml_path.exists():
        log.warning("[prompts] %s not found, using minimal fallback", yaml_path)
        return _fallback_prompt(agent_name)

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return PromptConfig(
            persona=data.get("persona", agent_name),
            role=data.get("role", ""),
            system_prompt=data.get("system_prompt", ""),
            temperature=float(data.get("temperature", 0.7)),
            max_tokens=int(data.get("max_tokens", 2000)),
        )
    except Exception as e:
        log.error("[prompts] Failed to load %s: %s", yaml_path, e)
        return _fallback_prompt(agent_name)


def _fallback_prompt(agent_name: str) -> PromptConfig:
    """Minimal inline fallbacks if YAML files are missing."""
    fallbacks: dict[str, PromptConfig] = {
        "strategist": PromptConfig(
            persona="Aura Vance",
            role="Chief Brand Strategist",
            system_prompt=(
                "Analyze the given content and return a JSON strategic brief with keys: "
                "angle, audience, tone, visual_direction, platform_notes."
            ),
            temperature=0.7,
            max_tokens=1500,
        ),
        "copywriter": PromptConfig(
            persona="Julian Sterling",
            role="Lead Brand Wordsmith",
            system_prompt=(
                "Write platform-optimized copy and return JSON with keys: "
                "headline, subhead, body, tagline, badge. No emojis."
            ),
            temperature=0.75,
            max_tokens=2000,
        ),
        "designer": PromptConfig(
            persona="Marcus Chen",
            role="Senior Visual Designer",
            system_prompt=(
                "Create a standalone HTML document for the given platform. "
                "Use CSS variables (var(--color-*)) only. No Tailwind. Return HTML only."
            ),
            temperature=0.7,
            max_tokens=8192,
        ),
        "verifier": PromptConfig(
            persona="Victoria Thorne",
            role="Design Quality Director",
            system_prompt=(
                "Audit the rendered design image and return JSON with: "
                "pass (bool), score (0-100), issues (list), critique (string)."
            ),
            temperature=0.3,
            max_tokens=1000,
        ),
    }
    return fallbacks.get(
        agent_name,
        PromptConfig(
            persona=agent_name,
            role="AI Agent",
            system_prompt="You are a helpful AI agent.",
        ),
    )
