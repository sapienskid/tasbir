"""Template node tests — user template override, auto-fallback, logo context."""

import asyncio

from app.agents.orchestrator.nodes.template_renderer import template_node_single
from app.agents.orchestrator.state import initial_state
from app.db.session import get_shared_session_factory
from app.services.design_systems import load_ds_templates
from app.services.seeding import seed_default_design_system

COPY = '{"headline":"H","subhead":"","body":"B","tagline":"","badge":null}'


def _state(**kw):
    return initial_state(
        title="T",
        content="C",
        platforms=["instagram-square", "linkedin-post"],
        _task_id="tpl-node-test",
        footer={"left": "A", "right": "@B"},
        categories=[{"name": "WRITING"}],
        category="WRITING",
        ground="white",
        **kw,
    )


async def _templates():
    pool = await get_shared_session_factory()
    await seed_default_design_system(pool)
    return await load_ds_templates(pool, "default")


def test_user_template_override():
    async def run():
        templates = await _templates()
        square = next(t for t in templates if t["family"] == "square")
        state = _state(ds_templates=templates, template_id=square["id"])
        state["_processing_format_id"] = "instagram-square"
        state["format_tasks"]["instagram-square"]["copy"] = COPY
        out = await template_node_single(state)
        ft = out["format_tasks"]["instagram-square"]
        assert ft["template_id"] == square["id"]
        assert ft["status"] == "html_ready"
        assert "data-slot=" in ft["html"]

    asyncio.run(run())


def test_auto_fallback_for_other_family():
    """A user square pick falls back to a landscape template for LinkedIn."""

    async def run():
        templates = await _templates()
        square = next(t for t in templates if t["family"] == "square")
        state = _state(ds_templates=templates, template_id=square["id"])
        state["_processing_format_id"] = "linkedin-post"
        state["format_tasks"]["linkedin-post"]["copy"] = COPY
        out = await template_node_single(state)
        ft = out["format_tasks"]["linkedin-post"]
        assert ft["template_id"] != square["id"]
        assert ft["template_id"].startswith("landscape-")
        assert ft["status"] == "html_ready"

    asyncio.run(run())


def test_per_platform_template_override_wins_over_global():
    """A platform's template_id beats the post-wide template_id for that format."""

    async def run():
        templates = await _templates()
        square = next(t for t in templates if t["family"] == "square")
        landscape = next(t for t in templates if t["family"] == "landscape")
        state = _state(
            ds_templates=templates,
            template_id=landscape["id"],
            platforms_config={"instagram-square": {"template_id": square["id"]}},
        )
        state["_processing_format_id"] = "instagram-square"
        state["format_tasks"]["instagram-square"]["copy"] = COPY
        out = await template_node_single(state)
        ft = out["format_tasks"]["instagram-square"]
        assert ft["template_id"] == square["id"]
        assert ft["status"] == "html_ready"

    asyncio.run(run())


def test_carousel_slide_resolves_base_platform_override():
    """instagram-carousel-N honors the base platform's platforms_config entry."""

    async def run():
        templates = await _templates()
        square = next(t for t in templates if t["family"] == "square")
        state = _state(
            ds_templates=templates,
            platforms_config={"instagram-carousel": {"template_id": square["id"]}},
        )
        state["_processing_format_id"] = "instagram-carousel-1"
        state["format_tasks"]["instagram-carousel-1"] = {"copy": COPY}
        out = await template_node_single(state)
        ft = out["format_tasks"]["instagram-carousel-1"]
        assert ft["template_id"] == square["id"]
        assert ft["status"] == "html_ready"

    asyncio.run(run())


def test_logo_passed_into_context():
    async def run():
        templates = await _templates()
        state = _state(
            ds_templates=templates, logo="data:image/png;base64,AAAA"
        )
        state["_processing_format_id"] = "instagram-square"
        state["format_tasks"]["instagram-square"]["copy"] = COPY
        out = await template_node_single(state)
        assert out["format_tasks"]["instagram-square"]["status"] == "html_ready"

    asyncio.run(run())


def test_no_templates_returns_empty():
    async def run():
        state = _state(ds_templates=[])
        state["_processing_format_id"] = "instagram-square"
        state["format_tasks"]["instagram-square"]["copy"] = COPY
        out = await template_node_single(state)
        assert out == {}

    asyncio.run(run())
