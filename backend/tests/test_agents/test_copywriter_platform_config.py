"""Copywriter per-platform post_type resolution tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.state import initial_state


def _async_ret(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


_CFG = SimpleNamespace(system_prompt="sys", temperature=0.4, max_tokens=400)

_LLM_RESPONSE = '{"headline":"H","subhead":"S","body":"B","tagline":"","badge":null}'


async def _run(platforms, platforms_config, post_type="default"):
    captured: dict[str, str] = {}

    async def fake_call_llm(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        captured[user_prompt] = user_prompt
        return _LLM_RESPONSE

    with patch(
        "app.agents.orchestrator.nodes.copywriter.call_llm", fake_call_llm
    ), patch(
        "app.agents.orchestrator.nodes.copywriter.get_agent_config", _async_ret(_CFG)
    ):
        state = initial_state(
            title="T",
            content="C",
            platforms=platforms,
            _task_id="",
            design_tokens={},
            brand_info={"name": "Acme"},
            campaign={},
            overrides={},
            images=[],
            footer={},
            categories=[],
            category="",
            ground="white",
            post_type=post_type,
            platforms_config=platforms_config,
        )
        await copywriter_node(state)
    return captured


def _prompt_for(captured: dict[str, str], platform: str) -> str:
    for p in captured.values():
        if f"PLATFORM: {platform} " in p:
            return p
    raise AssertionError(f"no user prompt captured for {platform}: {list(captured.keys())}")


def test_per_platform_post_type_resolution():
    captured = asyncio.run(_run(
        ["instagram-square", "linkedin-post"],
        {
            "instagram-square": {"post_type": "quote"},
            "linkedin-post": {"post_type": "tutorial"},
        },
        post_type="default",
    ))
    square = _prompt_for(captured, "instagram-square")
    linkedin = _prompt_for(captured, "linkedin-post")
    assert "POST TYPE: quote" in square
    assert "extra.source" in square
    assert "POST TYPE: tutorial" in linkedin
    assert "extra.stat" in linkedin
    # no cross-contamination
    assert "POST TYPE: tutorial" not in square
    assert "POST TYPE: quote" not in linkedin


def test_global_post_type_fallback():
    captured = asyncio.run(_run(
        ["instagram-square", "linkedin-post"],
        {},
        post_type="promo",
    ))
    for platform in ("instagram-square", "linkedin-post"):
        prompt = _prompt_for(captured, platform)
        assert "POST TYPE: promo" in prompt
        assert "extra.cta" in prompt
