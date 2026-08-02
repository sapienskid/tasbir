"""Template library tests — catalog, selection, Jinja2 fill, slotize, promote."""

import pytest

from app.services.templates import (
    build_template_context,
    extract_slots,
    format_family,
    load_template_catalog,
    render_template_file,
    select_template,
    slotize_html,
)

FOOTER = {"left": "SABIN POKHAREL", "right": "@SAPIENSKID"}
COPY = {
    "headline": "A Quiet Column of Type",
    "subhead": "White space is not emptiness; it is the rhythm between ideas.",
    "body": "A grid sets order; a measure sets pace. Constrain the line, free the reader.",
    "tagline": "No. 12",
    "badge": None,
}
DIMS = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
    "landscape": (1200, 627),
}


def _render(tid, family, ground="white", copy=None, seed="test", has_image=False):
    entry = load_template_catalog()["templates"][tid]
    w, h = DIMS[family]
    ctx = build_template_context(
        copy or COPY, "WRITING", ground, FOOTER, w, h, has_image, seed=seed, family=family
    )
    return render_template_file(entry["file"], ctx)


def _catalog_templates() -> list[dict]:
    """Catalog entries shaped like DB template dicts (with ``id``)."""
    return [
        {"id": tid, **entry}
        for tid, entry in load_template_catalog()["templates"].items()
    ]


def test_family_type_scale():
    import asyncio

    from app.services.design_systems import default_design_system_payload

    di_config = asyncio.run(default_design_system_payload()).get("design_instruction") or {}

    def scale(family, w, h):
        ctx = build_template_context(
            {"headline": "x"}, "", "white", {}, w, h, False, family=family, di_config=di_config
        )
        return ctx["tscale"]

    assert scale("square", 1080, 1080) == 1.0
    assert scale("portrait", 1080, 1350) > 1.0
    assert scale("story", 1080, 1920) > scale("portrait", 1080, 1350)
    # landscape stays equivalent to its old width-based sizing (1200/1080).
    assert abs(scale("landscape", 1200, 627) - 1200 / 1080) < 1e-6


class TestCatalog:
    def test_all_templates_render(self):
        catalog = load_template_catalog()["templates"]
        assert len(catalog) >= 10
        for tid, entry in catalog.items():
            family = entry["family"]
            assert family in DIMS
            html = _render(tid, family)
            assert "<style" in html
            assert "data-slot=" in html
            assert "var(--color-" in html

    def test_canvas_size_is_parametric(self):
        html = _render("square-editorial-stack", "square")
        assert "width: 1080px" in html
        assert "height: 1080px" in html


class TestSelection:
    def test_family_filter(self):
        selection = select_template("square", "white", "NOTE", "", "seed", _catalog_templates())
        assert selection is not None
        assert selection[0].startswith("square-")

    def test_ground_filter(self):
        selection = select_template("square", "black", "NOTE", "", "seed", _catalog_templates())
        assert selection is not None
        # NOTE + black should prefer index-numeral (weighted/category boost)
        assert selection[0] == "square-index-numeral"

    def test_no_match_for_unknown_family(self):
        assert select_template("octagonal", "white", "", "", "seed", _catalog_templates()) is None

    def test_category_boost(self):
        selection = select_template("landscape", "white", "PORTFOLIO", "", "seed", _catalog_templates())
        # PORTFOLIO maps to both landscape-split and landscape-ad-card.
        assert selection is not None
        assert selection[0] in {"landscape-split", "landscape-ad-card"}

    def test_hint_boost(self):
        selection = select_template("square", "white", "", "note-card", "seed", _catalog_templates())
        assert selection[0] == "square-note-card"

    def test_deterministic(self):
        a = select_template("square", "white", "", "", "the-same-seed", _catalog_templates())
        b = select_template("square", "white", "", "", "the-same-seed", _catalog_templates())
        assert a == b

    def test_excludes_recent(self):
        first = select_template(
            "square", "white", "", "", "seed", _catalog_templates(),
            exclude={"square-editorial-stack"},
        )
        assert first is not None


class TestRendering:
    def test_copy_is_html_escaped(self):
        html = _render(
            "square-editorial-stack",
            "square",
            copy={**COPY, "headline": "<script>alert(1)</script>"},
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_optional_image_slot(self):
        with_img = _render("portrait-index", "portrait", has_image=True)
        assert "data-image-key=" in with_img
        without_img = _render("portrait-index", "portrait", has_image=False)
        assert "data-image-key=" not in without_img

    def test_black_ground_attribute(self):
        html = _render("square-note-card", "square", ground="black")
        assert 'data-ground="black"' in html


class TestPromotion:
    def test_extract_slots(self):
        html = _render("square-index-numeral", "square")
        slots = extract_slots(html)
        assert slots["headline"] == COPY["headline"]
        assert slots["footer_left"] == "SABIN POKHAREL"

    def test_slotize_roundtrip(self):
        tid, family = "square-index-numeral", "square"
        html = _render(tid, family, ground="black")
        tpl = slotize_html(html)
        assert "{{ headline }}" in tpl
        assert 'data-slot="headline"' in tpl
        assert "{% if ground" in tpl
        assert "<!DOCTYPE html>" in tpl

    def test_slotize_parameterizes_canvas(self):
        html = _render("landscape-split", "landscape")
        tpl = slotize_html(html)
        assert "width: {{ width }}px" in tpl
        assert "height: {{ height }}px" in tpl

    def test_slotize_strips_injected_blocks(self):
        html = _render("square-editorial-stack", "square")
        injected = (
            "<head><style>:root { --color-bg: #fff; }</style>"
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
            '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>'
        )
        combined = injected + html
        tpl = slotize_html(combined)
        assert ":root" not in tpl
        assert "#fff" not in tpl
        assert "fonts.googleapis" not in tpl
        assert "cdn.jsdelivr.net" not in tpl

    def test_render_promoted_template_roundtrip(self):
        from jinja2 import Environment

        html = _render("landscape-split", "landscape")
        tpl = slotize_html(html)
        env = Environment(autoescape=True)
        w, h = DIMS["landscape"]
        ctx = build_template_context(COPY, "WRITING", "white", FOOTER, w, h, False, seed="x")
        out = env.from_string(tpl).render(**ctx)
        assert COPY["headline"] in out
        assert COPY["body"] in out


def test_format_family_mapping():
    assert format_family("instagram-square") == "square"
    assert format_family("instagram-portrait") == "portrait"
    assert format_family("instagram-story") == "story"
    assert format_family("linkedin-post") == "landscape"
    assert format_family("twitter-card") == "landscape"


@pytest.mark.asyncio
async def test_no_template_overflows_at_max_copy():
    """Every template × ground must fit maximum-length copy.

    Requires the Playwright render service (reachable in the full stack);
    skipped when it is not available.
    """
    import httpx

    from app.services.dom_extractor import detect_overflow

    try:
        resp = httpx.get("http://playwright:4000/health", timeout=2)
        if resp.status_code != 200:
            pytest.skip("render service not reachable")
    except Exception:
        pytest.skip("render service not reachable")

    max_copy = {
        "headline": (
            "The measure of a column is the quiet contract between line and breath"
        ),
        "subhead": (
            "A grid sets order and a measure sets pace; constrain the line, free the reader."
        ),
        "body": (
            "Swiss design distills a message to its essence: black, white, and the space "
            "between. A column of serif type at a proper measure keeps the eye moving. "
            "Generous margins, tabular numerals, a hairline rule, and nothing else."
        ),
        "tagline": "No. 12 — On grid systems",
        "badge": None,
    }
    for tid, entry in load_template_catalog()["templates"].items():
        family = entry["family"]
        w, h = DIMS[family]
        for ground in ("white", "black"):
            ctx = build_template_context(
                dict(max_copy), "WRITING", ground, FOOTER, w, h, False, seed=tid, family=family
            )
            html = render_template_file(entry["file"], ctx)
            overflow = await detect_overflow(html, w, h)
            assert not overflow, f"{tid} ({ground}) overflows: {overflow}"
