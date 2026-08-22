"""Carousel support tests — slide expansion, formats, and copy splitting."""

import asyncio
import json
from contextlib import ExitStack

from app.agents.orchestrator.graph import (
    _extract_slides,
    _run_sequence_check,
    process_all_formats_node,
)
from app.agents.orchestrator.nodes.copywriter import _fallback_slides, _split_sentences
from app.agents.orchestrator.state import initial_state
from app.services.formats import (
    get_format_info,
    is_carousel,
    parse_carousel_slide,
)

# ─── Format helpers ─────────────────────────────────────────────────────────


def test_carousel_format_registered():
    info = get_format_info("instagram-carousel")
    assert (info.width, info.height) == (1080, 1080)


def test_slide_format_resolves_to_carousel_dims():
    assert is_carousel("instagram-carousel")
    assert is_carousel("instagram-carousel-3")
    assert not is_carousel("instagram-square")
    assert parse_carousel_slide("instagram-carousel-2") == ("instagram-carousel", 2)
    assert parse_carousel_slide("instagram-carousel") is None
    assert parse_carousel_slide("instagram-square") is None
    info = get_format_info("instagram-carousel-5")
    assert (info.width, info.height) == (1080, 1080)


# ─── Copy splitting helpers ─────────────────────────────────────────────────


def test_fallback_slides_produce_n_frames():
    slides = _fallback_slides(
        "First sentence. Second sentence. Third finding. Fourth insight.", "Title", 4
    )
    assert len(slides) == 4
    assert slides[0].headline == "Title"
    assert slides[0].body  # first slide carries the hook
    for s in slides:
        assert s.headline  # every slide has a headline (cover + derived)
        assert s.body  # every slide has substance


def test_derive_mini_headline_never_mid_sentence():
    from app.agents.orchestrator.nodes.copywriter import _derive_mini_headline

    long = (
        "The key insight from our latest research is that retention depends "
        "far more on daily habits than on the size of the initial push."
    )
    headline = _derive_mini_headline(long, "Title")
    # never a chopped fragment — either the full sentence or a clean break
    assert headline.startswith("The key insight")
    assert "daily habits" in headline
    assert not headline.endswith(("the", "of", "is", "than", "on"))


def test_truncate_sentence_aware_keeps_all_fitting_sentences():
    from app.agents.orchestrator.nodes.copywriter import _truncate_sentence_aware

    long = (
        "First finding is that retention follows habits. Second is that "
        "spacing strengthens memory. Third is that fewer reviews retain more."
    )
    cut = _truncate_sentence_aware(long, 120)
    # keeps every COMPLETE sentence that fits, no dangling ellipsis
    assert cut.startswith("First finding")
    assert cut.endswith("spacing strengthens memory.")
    assert "…" not in cut
    # run-on block with no sentence boundary falls back to a word cut + ellipsis
    runon = "a very long unbroken block of words with no punctuation at all " * 12
    runon_cut = _truncate_sentence_aware(runon, 80)
    assert runon_cut.endswith("…")
    assert len(runon_cut) <= 80


def test_derive_mini_headline_empty_body_uses_title():
    from app.agents.orchestrator.nodes.copywriter import _derive_mini_headline

    assert _derive_mini_headline("", "My Frame") == "My Frame"
    assert _derive_mini_headline("", "") == "Frame"


def test_finalize_slides_guarantees_headline_and_bounds_body():
    from app.agents.orchestrator.nodes.copywriter import SlideCopy, _finalize_slides

    long_body = "A very long sentence that goes on and on about typography and " * 12
    slides = [
        SlideCopy(headline="", subhead="", body=long_body, tagline="", badge=None),
        SlideCopy(headline="Real hook", subhead="", body="Short body.", tagline="", badge=None),
    ]
    out = _finalize_slides(slides, "Title")
    assert out[0].headline  # derived, non-empty
    assert len(out[0].body) <= 420  # generous cap, verifier is the real arbiter
    assert out[1].headline == "Real hook"
    assert out[1].body == "Short body."


def test_finalize_slides_keeps_multiple_complete_sentences():
    from app.agents.orchestrator.nodes.copywriter import SlideCopy, _finalize_slides

    body = (
        "The instinct is to blame the database. We added indexes and bought "
        "faster hardware. Nothing moved the needle. The real bottleneck was "
        "orchestration, not storage."
    )
    out = _finalize_slides(
        [SlideCopy(headline="", subhead="", body=body, tagline="", badge=None)], "Title"
    )
    assert out[0].body == body  # all sentences fit under the generous cap — no truncation
    assert "…" not in out[0].body


async def test_slide_with_missing_headline_key_is_repaired_not_fallback():
    """A slide lacking the headline key must NOT discard the whole LLM output."""
    import json as _json
    from unittest.mock import AsyncMock, patch

    from app.agents.orchestrator.nodes.copywriter import (
        PlatformCopy,
        _repair_slide_headlines,
    )

    slides = [
        PlatformCopy(
            headline="C",
            subhead="",
            body="",
            tagline="",
            badge=None,
            slides=[
                {"headline": "Cover", "subhead": "", "body": "Hook", "tagline": "", "badge": None},
                {
                    "subhead": "",
                    "body": "Second body.",
                    "tagline": "",
                    "badge": None,
                },  # no headline key
            ],
        ).slides
    ][0]
    assert slides[1].headline == ""  # optional field defaults to ""

    class Cfg:
        system_prompt = "x"
        temperature = 0.6
        max_tokens = 300

    async def repair_mock(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        assert "sharp editorial copywriter" in system_prompt
        assert "COMPLETE, self-contained mini-headline" in user_prompt
        return _json.dumps({"2": "Retention depends on daily habits"})

    with patch(
        "app.agents.orchestrator.nodes.copywriter.call_llm",
        new=AsyncMock(side_effect=repair_mock),
    ):
        out = await _repair_slide_headlines(slides, "My Title", "content", Cfg())

    assert out[1].headline == "Retention depends on daily habits"
    assert out[0].headline == "Cover"  # untouched


async def test_repair_pass_degrades_to_sentence_complete():
    """When the repair LLM fails, derived titles stay whole sentences."""
    from unittest.mock import AsyncMock, patch

    from app.agents.orchestrator.nodes.copywriter import (
        PlatformCopy,
        _finalize_slides,
        _repair_slide_headlines,
    )

    slides = PlatformCopy(
        headline="C",
        subhead="",
        body="",
        tagline="",
        badge=None,
        slides=[
            {"headline": "Cover", "subhead": "", "body": "Hook", "tagline": "", "badge": None},
            {
                "subhead": "",
                "body": "Retention follows daily habits, not first impressions.",
                "tagline": "",
                "badge": None,
            },
        ],
    ).slides

    class Cfg:
        temperature = 0.6
        max_tokens = 300

    async def boom(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        raise RuntimeError("quota")

    with patch(
        "app.agents.orchestrator.nodes.copywriter.call_llm",
        new=AsyncMock(side_effect=boom),
    ):
        out = await _repair_slide_headlines(slides, "My Title", "content", Cfg())
    out = _finalize_slides(out, "My Title")
    assert out[1].headline == "Retention follows daily habits"


async def test_repair_replaces_derived_first_words_of_body():
    """Padded/fallback titles that are just the body's first words get replaced."""
    import json as _json
    from unittest.mock import AsyncMock, patch

    from app.agents.orchestrator.nodes.copywriter import (
        PlatformCopy,
        _repair_slide_headlines,
    )

    body2 = (
        "Retention depends far more on daily habits than on the size of the "
        "initial push, and the same is true of most things that last."
    )
    slides = PlatformCopy(
        headline="C",
        subhead="",
        body="",
        tagline="",
        badge=None,
        slides=[
            {"headline": "Cover", "subhead": "", "body": "Hook", "tagline": "", "badge": None},
            {"headline": "", "subhead": "", "body": body2, "tagline": "", "badge": None},
        ],
    ).slides
    # Simulate a padded/fallback slide whose title equals its body's first words.
    slides[1] = slides[1].model_copy(
        update={"headline": "Retention depends far more on daily habits"}
    )

    class Cfg:
        temperature = 0.6
        max_tokens = 300

    async def repair_mock(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        return _json.dumps({"2": "Daily habits beat first impressions"})

    with patch(
        "app.agents.orchestrator.nodes.copywriter.call_llm",
        new=AsyncMock(side_effect=repair_mock),
    ):
        out = await _repair_slide_headlines(slides, "My Title", "content", Cfg())

    assert out[1].headline == "Daily habits beat first impressions"
    assert out[0].headline == "Cover"  # authored headline untouched


def test_split_sentences_respects_count():
    chunks = _split_sentences("One. Two. Three. Four. Five. Six. Seven. Eight.", 4)
    assert len(chunks) == 4
    assert all(c.strip() for c in chunks)


def test_extract_slides_parses_carousel_copy():
    copy = json.dumps(
        {
            "slides": [
                {"headline": "C1", "subhead": "", "body": "B1", "tagline": "", "badge": None},
                {"headline": "C2", "subhead": "", "body": "B2", "tagline": "", "badge": None},
            ]
        }
    )
    slides = _extract_slides(copy)
    assert len(slides) == 2
    assert slides[0]["headline"] == "C1"


def test_extract_slides_empty_on_plain_copy():
    assert _extract_slides('{"headline":"H","body":"B"}') == []
    assert _extract_slides("not json") == []
    assert _extract_slides("") == []


# ─── Pipeline expansion ──────────────────────────────────────────────────────


def _carousel_state():
    state = initial_state(
        title="T",
        content="C",
        platforms=["instagram-carousel"],
        slides=3,
        _task_id="test-carousel",
        design_tokens={
            "--color-bg": "#FFFFFF",
            "--color-text": "#000000",
            "--color-border": "#D9D9D9",
            "--color-bg-inverted": "#000000",
            "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#6E6E6E",
            "--font-sans": "Inter",
            "--font-display": "Space Grotesk",
        },
        footer={"left": "A", "right": "@B"},
        categories=[{"name": "WRITING"}],
    )
    state["format_tasks"]["instagram-carousel"]["copy"] = json.dumps(
        {
            "slides": [
                {"headline": "C1", "subhead": "", "body": "B1", "tagline": "", "badge": None},
                {"headline": "C2", "subhead": "", "body": "B2", "tagline": "", "badge": None},
                {"headline": "C3", "subhead": "", "body": "B3", "tagline": "", "badge": None},
            ]
        }
    )
    return state


def _patches():
    import re

    def good_html(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        m = re.search(r"CANVAS: (\d+)px × (\d+)px", user_prompt)
        w, h = (m.group(1), m.group(2)) if m else ("1080", "1080")
        return (
            "<html><head><style>"
            f"body{{width:{w}px;height:{h}px;background:var(--color-bg);"
            "color:var(--color-text);font-family:var(--font-sans)}}"
            ".kicker{text-transform:uppercase}"
            ".headline{font-family:var(--font-display)}"
            ".wordmark{font-family:var(--font-display)}"
            "</style></head>"
            f'<body style="width:{w}px;height:{h}px;overflow:hidden;margin:0">'
            '<div class="kicker">WRITING</div><h1 class="headline">Hello World Headline</h1>'
            '<div class="footer"><span class="wordmark">A</span><span>@B</span></div></body></html>'
        )

    from unittest.mock import AsyncMock, patch

    return (
        patch(
            "app.agents.orchestrator.nodes.designer.call_llm", new=AsyncMock(side_effect=good_html)
        ),
        patch(
            "app.agents.orchestrator.nodes.quality_check.render_to_png",
            new=AsyncMock(return_value=b"PNG"),
        ),
        patch(
            "app.agents.orchestrator.nodes.quality_check._call_vision_llm",
            new=AsyncMock(return_value='{"pass":true,"score":90,"issues":[],"critique":"ok"}'),
        ),
        patch("app.services.media_plan.build_media_plan", new=AsyncMock(return_value={})),
    )


def test_process_all_formats_expands_carousel_into_slides():
    state = _carousel_state()
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))

    fts = out["format_tasks"]
    assert set(fts.keys()) == {
        "instagram-carousel-1",
        "instagram-carousel-2",
        "instagram-carousel-3",
    }
    for sid, ft in fts.items():
        assert ft["status"] == "verified", f"{sid}: {ft['status']}"
        assert ft["quality_score"] >= 80
        # each slide's copy is its own frame
        assert json.loads(ft["copy"])["headline"].startswith("C")
    assert out["verification"]["instagram-carousel-1"]["pass"] is True


def test_carousel_expansion_assigns_slide_context():
    state = _carousel_state()
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))

    # slide_context is carried on the merged state through the chain slices
    assert out["retry_count"]  # merged deterministically
    for sid in ("instagram-carousel-1", "instagram-carousel-3"):
        assert sid in out["verification"]


# ─── Sequence check (deterministic, no vision) ──────────────────────────────


def _seq_state(slides: list[str], htmls: dict[str, str]) -> dict:
    state = initial_state(
        title="T",
        content="C",
        platforms=["instagram-carousel"],
        _task_id="",
        slides=len(slides),
        ratio="square",
    )
    state["slide_context"] = {
        sid: {"index": i, "total": len(slides)} for i, sid in enumerate(slides, start=1)
    }
    state["format_tasks"] = {
        sid: {"html": htmls.get(sid, ""), "status": "verified"} for sid in slides
    }
    return state


async def test_sequence_check_detects_missing_counter():
    state = _seq_state(
        ["instagram-carousel-1", "instagram-carousel-2"],
        {
            "instagram-carousel-1": "<html><body>1/2</body></html>",
            "instagram-carousel-2": "<html><body>no counter</body></html>",
        },
    )
    out = await _run_sequence_check(state)
    assert out["ok"]
    assert any("no '2/2' slide counter" in w for w in out["warnings"])


async def test_sequence_check_skips_non_carousel():
    state = initial_state(
        title="T",
        content="C",
        platforms=["instagram-square"],
        _task_id="",
    )
    assert await _run_sequence_check(state) == {}


def test_process_all_formats_includes_sequence_check():
    state = _carousel_state()
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))

    seq = out["sequence_check"]
    # Sequence check ran because slide_context was populated.
    assert isinstance(seq, dict)
    # Designer output has no "i/N" counter → soft warnings, not failures.
    assert seq["ok"] is True
    assert any("slide counter" in w for w in seq["warnings"])


def test_portrait_carousel_expands_under_portrait_base():
    state = initial_state(
        title="T",
        content="C",
        platforms=["instagram-carousel-portrait"],
        slides=2,
        _task_id="test-portrait-carousel",
        design_tokens={
            "--color-bg": "#FFFFFF",
            "--color-text": "#000000",
            "--color-border": "#D9D9D9",
            "--font-sans": "Inter",
            "--font-display": "Space Grotesk",
        },
        footer={"left": "A", "right": "@B"},
        categories=[{"name": "WRITING"}],
    )
    state["format_tasks"]["instagram-carousel-portrait"]["copy"] = json.dumps(
        {
            "slides": [
                {"headline": "P1", "subhead": "", "body": "B1", "tagline": "", "badge": None},
                {"headline": "P2", "subhead": "", "body": "B2", "tagline": "", "badge": None},
            ]
        }
    )

    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))

    assert set(out["format_tasks"].keys()) == {
        "instagram-carousel-portrait-1",
        "instagram-carousel-portrait-2",
    }
    # Slides resolve to the portrait dims (1080x1350).
    assert get_format_info("instagram-carousel-portrait-1").height == 1350
    assert get_format_info("instagram-carousel-portrait-1").width == 1080


# ─── Copywriter resilience (never drop a platform) ──────────────────────────


def test_fallback_copy_uses_title_not_untitled():
    from app.agents.orchestrator.nodes.copywriter import _fallback_copy

    c = _fallback_copy("Some real body text.", "My Great Title", 0, False)
    assert c.headline == "My Great Title"
    assert "real body" in c.body

    c2 = _fallback_copy("", "Title only", 0, False)
    assert c2.headline == "Title only"

    car = _fallback_copy("Body", "Title", 3, True)
    assert len(car.slides) == 3
    assert car.slides[0].headline == "Title"


async def test_copywriter_keeps_platform_when_llm_fails():
    """A failed copywriter LLM call yields title-based copy, not a dropped format."""
    from unittest.mock import AsyncMock, patch

    from app.agents.orchestrator.nodes.copywriter import copywriter_node

    async def boom(**kw):
        raise RuntimeError("quota exhausted")

    state = initial_state(
        title="The Measure",
        content="A grid sets order and a measure sets pace.",
        platforms=["instagram-square", "linkedin-post"],
        _task_id="",
        design_tokens={},
        brand_info={},
        campaign={},
        overrides={},
        images=[],
        footer={},
        categories=[{"name": "WRITING"}],
        category="WRITING",
        ground="white",
    )
    state["strategic_brief"] = {"angle": "A", "platform_notes": {}}

    with patch(
        "app.agents.orchestrator.nodes.copywriter.call_llm",
        new=AsyncMock(side_effect=boom),
    ):
        out = await copywriter_node(state)

    ft = out["format_tasks"]
    assert set(ft.keys()) == {"instagram-square", "linkedin-post"}
    for fmt, task in ft.items():
        copy = json.loads(task["copy"])
        assert copy["headline"] == "The Measure"
        assert copy["body"]
