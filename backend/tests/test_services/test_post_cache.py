"""Tests for the shared per-post media cache."""

import asyncio

import pytest

from app.agents.orchestrator.post_cache import post_cache_clear, post_cached


@pytest.mark.asyncio
async def test_post_cached_runs_loader_once():
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        await asyncio.sleep(0.01)
        return "svg-1"

    a = await post_cached("task-a", "illustration", loader)
    b = await post_cached("task-a", "illustration", loader)
    assert (a, b) == ("svg-1", "svg-1")
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_post_cached_concurrent_races():
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return "v"

    results = await asyncio.gather(
        *(post_cached("task-b", "photo", loader) for _ in range(8))
    )
    assert all(r == "v" for r in results)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_post_cached_separate_keys_and_clear():
    async def loader_a():
        return "a"

    async def loader_b():
        return "b"

    assert await post_cached("task-c", "k1", loader_a) == "a"
    assert await post_cached("task-c", "k2", loader_b) == "b"
    post_cache_clear("task-c")
    assert await post_cached("task-c", "k1", loader_a) == "a"
