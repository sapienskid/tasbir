"""Tests for v3 YAML prompt registry."""

import pytest
from app.agents.prompts.registry import load_prompt, PromptConfig


def test_load_strategist_prompt():
    cfg = load_prompt("strategist")
    assert isinstance(cfg, PromptConfig)
    assert cfg.persona == "Aura Vance"
    assert "Aura Vance" in cfg.system_prompt
    assert len(cfg.system_prompt) > 100
    assert cfg.temperature > 0
    assert cfg.max_tokens > 0


def test_load_copywriter_prompt():
    cfg = load_prompt("copywriter")
    assert "Julian Sterling" in cfg.persona
    assert "headline" in cfg.system_prompt.lower()
    assert cfg.temperature > 0


def test_load_designer_prompt():
    cfg = load_prompt("designer")
    assert "Marcus Chen" in cfg.persona
    assert "CSS" in cfg.system_prompt or "var(--" in cfg.system_prompt
    assert cfg.max_tokens >= 4000


def test_load_verifier_prompt():
    cfg = load_prompt("verifier")
    assert "Victoria Thorne" in cfg.persona
    assert cfg.temperature <= 0.5  # verifier should be more deterministic


def test_load_unknown_prompt_fallback():
    """Unknown agent names should return a fallback, not raise."""
    cfg = load_prompt("nonexistent_agent_xyz")
    assert isinstance(cfg, PromptConfig)
    assert cfg.system_prompt  # not empty


def test_prompt_config_has_all_fields():
    cfg = load_prompt("strategist")
    assert hasattr(cfg, "persona")
    assert hasattr(cfg, "role")
    assert hasattr(cfg, "system_prompt")
    assert hasattr(cfg, "temperature")
    assert hasattr(cfg, "max_tokens")


def test_strategist_prompt_outputs_json():
    """Strategist prompt must instruct for JSON output."""
    cfg = load_prompt("strategist")
    assert "json" in cfg.system_prompt.lower() or "JSON" in cfg.system_prompt


def test_copywriter_no_emoji_rule():
    """Copywriter prompt must ban emojis."""
    cfg = load_prompt("copywriter")
    assert "emoji" in cfg.system_prompt.lower() or "NO emoji" in cfg.system_prompt


def test_designer_no_tailwind_rule():
    """Designer prompt must prohibit Tailwind."""
    cfg = load_prompt("designer")
    assert "tailwind" in cfg.system_prompt.lower() or "Tailwind" in cfg.system_prompt


def test_designer_css_variables_rule():
    """Designer prompt must enforce CSS variable usage."""
    cfg = load_prompt("designer")
    assert "var(--" in cfg.system_prompt or "CSS variable" in cfg.system_prompt.lower()
