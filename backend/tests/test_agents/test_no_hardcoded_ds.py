"""Guarantee no design-system content is hardcoded into agents.

Prompts (config/prompts/*.yaml) and agent prompt-assembly code must reference
the design system dynamically — via {TEMPLATE_CONTEXT}, node-injected blocks,
or the token/design-instruction services — never embed hex values, font
faces, brand identity strings, category labels, or token values as literals.

Allowed exceptions (single source of truth, not agent code):
- brand_vision/brand_tokens prompts: OUTPUT-SCHEMA examples (these agents
  exist to CREATE design systems and must show the hex/font shape).
- The design-system seed data in the service layer (tokens.py
  DEFAULT_TOKEN_VALUES, design_instruction.py, data/design_system/*.yaml).
"""

import re
from pathlib import Path

import pytest

from app.services.tokens import DEFAULT_TOKEN_VALUES

REPO = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO / "config" / "prompts"

# Hex / font literals in these are legitimate output schemas for the brand
# builder (they teach the model the token-shape it must emit).
SCHEMA_PROMPTS = {"brand_vision.yaml", "brand_tokens.yaml"}

_FONT_FACES = [
    "Space Grotesk",
    "Source Serif",
    "Helvetica Neue",
    "Inter,",
    "Georgia,",
    "Archivo",
    "JetBrains",
    "Roboto",
    "Open Sans",
    "IBM Plex",
]

# Brand identity / default-category literals that must never appear in prompts.
_BRAND_LITERALS = ["SABIN", "SAPIENSKID", "sapienskid", "PORTFOLIO", "THE LIMITS"]

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_TOKEN_REF_RE = re.compile(r"--[a-zA-Z0-9-]+\*?")

# Agent prompt-assembly code must stay DS-free. These files may hold seed data
# that legitimately contains design content (brand_agent DEFAULT_CATEGORIES,
# template_author SAMPLE_COPY) — the checks below target hex/faces only.
AGENT_FILES = [
    "app/agents/orchestrator/nodes/strategist.py",
    "app/agents/orchestrator/nodes/copywriter.py",
    "app/agents/orchestrator/nodes/designer.py",
    "app/agents/orchestrator/nodes/quality_check.py",
    "app/services/chat.py",
    "app/services/brand_agent.py",
    "app/services/template_author.py",
    "app/services/prompt_preview.py",
]

_KNOWN_TOKENS = set(DEFAULT_TOKEN_VALUES) | {
    # Optional accent tokens: only present when a (non-monochrome) design
    # system defines them, but prompts may reference them generically.
    "--color-accent",
    "--color-accent-secondary",
}


def _prompt_files():
    return sorted(p for p in PROMPTS_DIR.glob("*.yaml"))


def _violations(text: str, allow_hex: bool = False) -> list[str]:
    out: list[str] = []
    if not allow_hex:
        for m in _HEX_RE.findall(text):
            out.append(f"hex color literal {m!r}")
    for face in _FONT_FACES:
        if face.lower() in text.lower():
            out.append(f"font face literal {face!r}")
    return out


def test_prompts_have_no_design_system_literals():
    for path in _prompt_files():
        text = path.read_text(encoding="utf-8")
        if path.name not in SCHEMA_PROMPTS:
            for v in _violations(text):
                pytest.fail(f"{path.name}: {v}")
        for lit in _BRAND_LITERALS:
            assert lit not in text, f"{path.name}: brand/category literal {lit!r}"


def test_prompt_token_references_are_known_or_wildcards():
    """Prompts may only name tokens from the DS contract, or use wildcards."""
    for path in _prompt_files():
        if path.name in SCHEMA_PROMPTS:
            continue
        text = path.read_text(encoding="utf-8")
        for ref in _TOKEN_REF_RE.findall(text):
            if ref.endswith("*"):
                continue  # wildcard pattern (e.g. var(--color-*))
            assert ref in _KNOWN_TOKENS, (
                f"{path.name}: token reference {ref!r} is not part of the "
                f"design-system contract"
            )


def test_agent_code_has_no_design_system_literals():
    for rel in AGENT_FILES:
        path = REPO / rel
        assert path.exists(), f"missing file {rel}"
        text = path.read_text(encoding="utf-8")
        for v in _violations(text):
            pytest.fail(f"{rel}: {v}")


def test_carousel_dims_not_hardcoded_in_copy_or_design():
    for rel in ("app/agents/orchestrator/nodes/copywriter.py",
                "app/agents/orchestrator/nodes/designer.py"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "1080x1080" not in text, f"{rel}: carousel dims hardcoded"
        assert "1080x1350" not in text, f"{rel}: carousel dims hardcoded"
