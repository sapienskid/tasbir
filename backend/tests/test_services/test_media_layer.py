"""Tests for the media-layer features: slide-number numerals, per-slide user
image distribution, and the duplicate-media QC guard."""

import json

from app.agents.orchestrator.graph import _duplicate_media_slides
from app.agents.orchestrator.state import initial_state
from app.services.templates import build_template_context


def test_loop_index_is_slide_number_on_carousels():
    ctx = build_template_context(
        {"headline": "x", "subhead": "", "body": "", "tagline": ""},
        "WRITING", "white", {}, 1080, 1080, False, seed="any|slide", slide_index=3, slide_total=5,
    )
    assert ctx["loop_index"] == 3


def test_loop_index_seeded_random_on_single_posts():
    a = build_template_context(
        {"headline": "x", "subhead": "", "body": "", "tagline": ""},
        "WRITING", "white", {}, 1080, 1080, False, seed="post-a",
    )
    b = build_template_context(
        {"headline": "x", "subhead": "", "body": "", "tagline": ""},
        "WRITING", "white", {}, 1080, 1080, False, seed="post-a",
    )
    assert a["loop_index"] == b["loop_index"]
    assert 1 <= a["loop_index"] <= 27


def test_duplicate_media_detection():
    """Two slides sharing a base64 image are flagged; the first is kept."""
    img = "data:image/jpeg;base64,AAAA//4AAAAAAAA="
    state = initial_state(title="t", content="c", platforms=["instagram-carousel"], slides=2)
    state["slide_context"] = {
        "instagram-carousel-1": {"index": 1, "total": 2},
        "instagram-carousel-2": {"index": 2, "total": 2},
    }
    state["format_tasks"] = {
        "instagram-carousel-1": {"html": f"<img src=\"{img}\">"},
        "instagram-carousel-2": {"html": f"<img src=\"{img}\">"},
    }
    dup = _duplicate_media_slides(state)
    assert dup == ["instagram-carousel-2"]


def test_duplicate_media_distinct_not_flagged():
    state = initial_state(title="t", content="c", platforms=["instagram-carousel"], slides=2)
    state["slide_context"] = {
        "instagram-carousel-1": {"index": 1, "total": 2},
        "instagram-carousel-2": {"index": 2, "total": 2},
    }
    state["format_tasks"] = {
        "instagram-carousel-1": {"html": '<img src="data:image/png;base64,AAAA">'},
        "instagram-carousel-2": {"html": '<img src="data:image/png;base64,BBBB">'},
    }
    assert _duplicate_media_slides(state) == []


def test_user_image_distribution_graph_side():
    """process_all_formats distributes image i → slide i (wrap)."""
    import asyncio
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, patch

    from app.agents.orchestrator.graph import process_all_formats_node

    slides = [
        {"headline": "C1", "subhead": "", "body": "B1", "tagline": "", "badge": None},
        {"headline": "C2", "subhead": "", "body": "B2", "tagline": "", "badge": None},
    ]
    state = initial_state(
        title="t", content="c", platforms=["instagram-carousel"], slides=2, ratio="square",
        _task_id="dup-task",
    )
    state["format_tasks"] = {
        "instagram-carousel": {
            "status": "waiting", "copy": json.dumps({"slides": slides}),
            "html": None, "html_path": None, "quality_score": 0,
            "quality_issues": [], "refinement_count": 0, "error": None, "template_id": None,
        }
    }
    state["images"] = [
        {"data": "img1", "mime": "image/png", "alt": "a"},
        {"data": "img2", "mime": "image/png", "alt": "b"},
    ]
    state["strategic_brief"] = {"content_summary": "x"}
    state["design_instruction"] = {"style": {"illustration_style": "compose"}}

    def good_html(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        import re
        m = re.search(r"CANVAS: (\d+)px × (\d+)px", user_prompt)
        w, h = (m.group(1), m.group(2)) if m else ("1080", "1080")
        return (
            '<html><head><style>'
            f'body{{width:{w}px;height:{h}px;background:var(--color-bg);'
            'color:var(--color-text);font-family:var(--font-sans)}}'
            '.kicker{text-transform:uppercase}.headline{font-family:var(--font-display)}'
            '.wordmark{font-family:var(--font-display)}</style></head>'
            f'<body style="width:{w}px;height:{h}px;overflow:hidden;margin:0">'
            '<div class="kicker">WRITING</div><h1 class="headline">Hello</h1>'
            '<img data-image-key="0" alt=""/>'
            '<div class="footer"><span class="wordmark">A</span><span>@B</span></div></body></html>'
        )

    with ExitStack() as stack:
        stack.enter_context(patch("app.agents.orchestrator.nodes.designer.call_llm",
                                  new=AsyncMock(side_effect=good_html)))
        stack.enter_context(patch("app.agents.orchestrator.nodes.quality_check.render_to_png",
                                  new=AsyncMock(return_value=b"PNG")))
        stack.enter_context(patch("app.agents.orchestrator.nodes.quality_check._call_vision_llm",
                                  new=AsyncMock(return_value='{"pass":true,"score":90,"issues":[],"critique":"ok"}')))
        stack.enter_context(patch("app.services.media_plan.build_media_plan",
                                  new=AsyncMock(return_value={})))
        out = asyncio.run(process_all_formats_node(state))

    # image i → slide i: slide 1 embeds image[0] (img1), slide 2 embeds img2.
    from pathlib import Path
    html1 = Path(out["format_tasks"]["instagram-carousel-1"]["html_path"]).read_text()
    html2 = Path(out["format_tasks"]["instagram-carousel-2"]["html_path"]).read_text()
    assert "img1" in html1
    assert "img2" in html2
    assert "img2" not in html1  # slide 1 must not show slide 2's image
    assert out["format_tasks"]["instagram-carousel-1"]["status"] == "verified"
    assert out["format_tasks"]["instagram-carousel-2"]["status"] == "verified"
