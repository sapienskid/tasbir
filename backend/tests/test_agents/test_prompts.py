"""Tests for prompt registry and default prompt loading."""

import pytest
from app.agents.prompts.registry import DEFAULT_PROMPTS, get_prompt, list_prompts


@pytest.mark.asyncio
async def test_default_prompts_exist():
    expected_agents = [
        "strategist",
        "copywriter",
        "visual_director",
        "designer",
        "quality_check",
        "token_generator",
    ]
    for agent in expected_agents:
        assert agent in DEFAULT_PROMPTS
        prompt = await get_prompt(agent)
        assert prompt.system_prompt is not None
        assert len(prompt.system_prompt) > 100


@pytest.mark.asyncio
async def test_strategist_prompt_persona():
    prompt = await get_prompt("strategist")
    assert "Aura Vance" in prompt.system_prompt
    assert "Creative Director" in prompt.system_prompt


@pytest.mark.asyncio
async def test_copywriter_prompt_persona():
    prompt = await get_prompt("copywriter")
    assert "Julian Sterling" in prompt.system_prompt
    assert "Headline" in prompt.system_prompt


@pytest.mark.asyncio
async def test_visual_director_prompt_persona():
    prompt = await get_prompt("visual_director")
    assert "Elena Rostova" in prompt.system_prompt


@pytest.mark.asyncio
async def test_designer_prompt_persona():
    prompt = await get_prompt("designer")
    assert "Marcus Chen" in prompt.system_prompt
    assert "<!DOCTYPE html>" in prompt.system_prompt


@pytest.mark.asyncio
async def test_quality_check_prompt_persona():
    prompt = await get_prompt("quality_check")
    assert "Victoria Thorne" in prompt.system_prompt


@pytest.mark.asyncio
async def test_list_prompts():
    prompts = await list_prompts()
    assert len(prompts) >= 6
