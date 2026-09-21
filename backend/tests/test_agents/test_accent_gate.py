"""Accent gate — an LLM-designed post in an accent language must use the accent."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.orchestrator.nodes import quality_check
from app.agents.orchestrator.nodes.quality_check import _accent_issues, quality_check_node_single
from app.services.styles import apply_style_preset, build_style_rules_block

ACCENT_DI = apply_style_preset("vibrant-pop", {})
SWISS_DI = apply_style_preset("swiss-editorial", {})

PLAIN = "<html><body><h1 style='color: var(--color-text)'>Hi</h1></body></html>"
WITH_ACCENT = (
    "<html><head><style>.bar{background: var(--color-accent)}</style></head>"
    "<body><div class='bar'></div></body></html>"
)
SECONDARY_ONLY = "<html><style>.b{border-color: var( --color-accent-secondary )}</style></html>"
TOKEN_DECL_ONLY = "<html><head><style>:root{--color-accent: #FF2D78}</style></head></html>"


def test_accent_language_without_accent_use_is_flagged():
    issues = _accent_issues(PLAIN, ACCENT_DI, None)
    assert len(issues) == 1 and "var(--color-accent)" in issues[0]


def test_token_declaration_alone_does_not_count():
    assert _accent_issues(TOKEN_DECL_ONLY, ACCENT_DI, None)


@pytest.mark.parametrize("html", [WITH_ACCENT, SECONDARY_ONLY])
def test_referencing_the_accent_passes(html):
    assert _accent_issues(html, ACCENT_DI, None) == []


def test_swiss_language_is_exempt():
    assert _accent_issues(PLAIN, SWISS_DI, None) == []
    assert _accent_issues(PLAIN, {}, None) == []


def test_template_posts_are_exempt():
    # Their accent devices are built into the template (gated by has_accent).
    assert _accent_issues(PLAIN, ACCENT_DI, "square-editorial-stack") == []


def test_rules_block_makes_the_accent_a_requirement():
    rules = build_style_rules_block(ACCENT_DI)
    assert "Accent: REQUIRED" in rules and "var(--color-accent)" in rules
    assert "never as a text colour" in rules
    assert "Accent: none" in build_style_rules_block(SWISS_DI)


def _state(html: str, di: dict, template_id: str | None = None) -> dict:
    task = {"html": html, "copy": "{}", "status": "html_ready"}
    if template_id:
        task["template_id"] = template_id
    return {
        "_processing_format_id": "instagram-square",
        "_task_id": "accent-gate-test",
        "format_tasks": {"instagram-square": task},
        "design_tokens": {"--font-display": "Inter, sans-serif"},
        "design_instruction": di,
        "footer": {"left": "", "right": "@B"},
        "category": "WRITING",
        "ground": "white",
        "retry_count": {},
        "verification": {},
    }


def test_verifier_sends_an_accent_less_designer_post_back(monkeypatch):
    monkeypatch.setattr(quality_check, "_save_html_preview", lambda *a, **k: None)
    out = asyncio.run(quality_check_node_single(_state(PLAIN, ACCENT_DI)))
    task = out["format_tasks"]["instagram-square"]
    verification = out["verification"]["instagram-square"]
    assert task["status"] == "needs_retry"
    assert verification["pass"] is False
    assert any("Design language requires its accent" in i for i in verification["issues"])
    assert "Fix:" in verification["critique"]
    assert out["retry_count"]["instagram-square"] == 1
