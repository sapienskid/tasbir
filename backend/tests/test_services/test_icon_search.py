"""Tests for the icon_search tool (deterministic catalog search)."""

import pytest

from app.services.tools.icon_search import (
    ICON_SEARCH_TOOL,
    format_icon_shortlist,
    icon_exists,
    search_icons,
)


@pytest.mark.asyncio
async def test_search_returns_content_relevant_names():
    """A subject keyword returns matching Lucide icon names."""
    names = search_icons("rocket launch")
    assert names and "rocket" in names


@pytest.mark.asyncio
async def test_search_matches_tags():
    """Tags in the catalog metadata steer results (e.g. 'leaf' topic)."""
    names = search_icons("leaf")
    assert names and "leaf" in names


@pytest.mark.asyncio
async def test_search_is_deterministic():
    """Same query → same ordered shortlist."""
    a = search_icons("book writing")
    b = search_icons("book writing")
    assert a == b and a


@pytest.mark.asyncio
async def test_search_garbage_returns_empty():
    """Unmatched gibberish returns an empty shortlist (no forced result)."""
    assert search_icons("zzzzqqqqlll") == []


@pytest.mark.asyncio
async def test_icon_exists():
    assert icon_exists("rocket")
    assert not icon_exists("definitely-not-an-icon")


@pytest.mark.asyncio
async def test_format_shortlist():
    out = format_icon_shortlist(["rocket", "arrow-up-right"])
    assert "[0] rocket" in out and "[1] arrow-up-right" in out
    assert format_icon_shortlist([]).startswith("No icons found")


@pytest.mark.asyncio
async def test_tool_schema():
    assert ICON_SEARCH_TOOL["function"]["name"] == "icon_search"
    assert "keywords" in ICON_SEARCH_TOOL["function"]["parameters"]["properties"]
