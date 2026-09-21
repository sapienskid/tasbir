"""Seed-template theming contract — accent / radius / shadow / display weight.

The 16 seed templates honour a design system's accent colour, corner radius,
shadow and headline weight WITHOUT changing how the accent-less (Swiss) default
renders:

* accent devices live only inside ``{% if has_accent %}`` (Jinja level), so an
  accent-less render carries no trace of ``--color-accent``;
* the accent is only ever a fill / rule / border / marker — never a text colour
  (a single accent cannot contrast with both grounds; ink-on-accent always can);
* a text-hosting chip renders only when its text is non-empty (``:not(:empty)``);
* headline / display weight reads ``--font-weight-display``.

Pixel-level identity of the accent-less render and the hard QC checks need a
browser / the render service, so they are verified outside pytest; these tests
guard the static contract.
"""

import re
from pathlib import Path

import pytest

from app.services.templates import (
    build_template_context,
    load_template_catalog,
    render_template_file,
)

FOOTER = {"left": "", "right": "@SAPIENSKID"}
COPY = {
    "headline": "Why small teams ship faster",
    "subhead": "Fewer handoffs beat more headcount, every time.",
    "body": "A team of four can decide in an afternoon what a team of forty debates.",
    "tagline": "",
    "extra": {},
}
DIMS = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
    "landscape": (1200, 627),
}
ACCENT_DI = {"style": {"accent": "accent"}}

# The one template whose headline is the serif editorial voice at weight 400
# (a quote, not the display face) — it deliberately does not follow the
# display-weight token.
DISPLAY_WEIGHT_EXEMPT = {"square-quote-card"}

# Properties that paint TEXT — the accent must never reach them.
TEXT_COLOUR_PROPS = {
    "color",
    "text-decoration-color",
    "-webkit-text-fill-color",
    "-webkit-text-stroke-color",
    "caret-color",
    "text-shadow",
}

_TEMPLATES_ROOT = Path(load_template_catalog()["templates"] and __file__).resolve()
_ROOT = Path(__file__).resolve().parents[2] / "data" / "design_system" / "templates"


def _catalog() -> dict[str, dict]:
    return load_template_catalog()["templates"]


def _ids() -> list[str]:
    return sorted(_catalog())


def _source(tid: str) -> str:
    return (_ROOT / _catalog()[tid]["file"]).read_text()


def _render(tid: str, *, accent: bool, ground: str = "white", kicker: str = "WRITING") -> str:
    entry = _catalog()[tid]
    family = entry["family"]
    w, h = DIMS[family]
    ctx = build_template_context(
        dict(COPY), kicker, ground, FOOTER, w, h, False,
        seed="theming", family=family, di_config=ACCENT_DI if accent else {},
    )
    return render_template_file(entry["file"], ctx)


# ---------------------------------------------------------------------------
# Jinja block scanner — finds the {% if has_accent %} regions of a source
# ---------------------------------------------------------------------------

_TAG = re.compile(r"\{%-?\s*(if|elif|else|endif|for|endfor|set|macro|endmacro)\b([^%]*?)-?%\}")


def _accent_regions(src: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of every ``{% if has_accent %}`` body.

    ``start`` is just after the opening tag, ``end`` just before the matching
    ``{% endif %}``. An ``else``/``elif`` branch of the accent ``if`` is *not*
    part of the region (it is the accent-less branch).
    """
    spans: list[tuple[int, int]] = []
    stack: list[dict] = []
    for m in _TAG.finditer(src):
        kw, rest = m.group(1), m.group(2).strip()
        if kw == "if":
            stack.append({"accent": rest == "has_accent", "start": m.end()})
        elif kw in ("elif", "else"):
            top = stack[-1]
            if top["accent"]:
                spans.append((top["start"], m.start()))
            top["accent"] = False
        elif kw == "endif":
            top = stack.pop()
            if top["accent"]:
                spans.append((top["start"], m.start()))
        # for/endfor/set/macro: not conditionals — ignored
    assert not stack, "unbalanced {% if %} in template source"
    return spans


def _strip_accent_blocks(src: str) -> str:
    """Remove every ``{% if has_accent %}...{% endif %}`` block from a source."""
    out, cursor = [], 0
    # Re-scan with full tag extents so the tags themselves are removed too.
    stack: list[dict] = []
    for m in _TAG.finditer(src):
        kw, rest = m.group(1), m.group(2).strip()
        if kw == "if":
            stack.append({"accent": rest == "has_accent", "open": m.start()})
        elif kw in ("elif", "else"):
            assert not stack[-1]["accent"], "has_accent block must not have else/elif"
        elif kw == "endif":
            top = stack.pop()
            if top["accent"] and not any(s["accent"] for s in stack):
                out.append(src[cursor : top["open"]])
                cursor = m.end()
    out.append(src[cursor:])
    return "".join(out)


# ---------------------------------------------------------------------------
# 1. Every template renders — accent on/off, both grounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tid", _ids())
@pytest.mark.parametrize("accent", [True, False])
@pytest.mark.parametrize("ground", ["white", "black"])
def test_renders_without_error(tid, accent, ground):
    html = _render(tid, accent=accent, ground=ground)
    assert "<html" in html and 'data-slot="headline"' in html
    assert ("{%" not in html) and ("{{" not in html)


# ---------------------------------------------------------------------------
# 2. Static guard — accent only inside has_accent, never a text colour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tid", _ids())
def test_accent_only_inside_has_accent_blocks(tid):
    src = _source(tid)
    regions = _accent_regions(src)
    for m in re.finditer(r"--color-accent", src):
        assert any(a <= m.start() < b for a, b in regions), (
            f"{tid}: --color-accent at offset {m.start()} is outside {{% if has_accent %}}"
        )


@pytest.mark.parametrize("tid", _ids())
def test_accent_never_a_text_colour(tid):
    src = _source(tid)
    # every "prop: ...--color-accent..." declaration (stylesheet or inline style)
    for m in re.finditer(r"([\w-]+)\s*:\s*[^;{}]*--color-accent", src):
        assert m.group(1).lower() not in TEXT_COLOUR_PROPS, (
            f"{tid}: '{m.group(1)}' uses --color-accent — the accent may only be a "
            "fill/border/rule, never a text colour"
        )


@pytest.mark.parametrize("tid", _ids())
def test_accent_text_hosts_are_ink_on_fill(tid):
    """A rule that puts the accent behind text must set ink (--color-text) on it."""
    src = _source(tid)
    for region in (src[a:b] for a, b in _accent_regions(src)):
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", region):
            if "--color-accent" not in body or "background" not in body:
                continue
            if "content:" in body:  # a pseudo-element bar/marker — no text inside
                continue
            assert re.search(r"(?<![-\w])color\s*:\s*var\(--color-text\)", body), (
                f"{tid}: '{sel.strip()[:60]}' fills with the accent but text on it is not "
                "var(--color-text)"
            )


@pytest.mark.parametrize("tid", _ids())
def test_accent_chips_need_text(tid):
    """Text-hosting accent fills / markers only apply to NON-empty elements."""
    src = _source(tid)
    hosts = re.compile(r"\.(kicker|mark|index|headline)\b|data-slot=\"kicker\"")
    for region in (src[a:b] for a, b in _accent_regions(src)):
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", region):
            if "--color-accent" not in body or "background" not in body:
                continue
            for part in (p.strip() for p in sel.split(",")):
                if hosts.search(part):
                    assert ":not(:empty)" in part, (
                        f"{tid}: accent rule '{part[:70]}' would paint an empty chip"
                    )


@pytest.mark.parametrize("tid", _ids())
def test_empty_kicker_keeps_the_kicker_element_empty(tid):
    """With no kicker the element stays truly empty, so ``:not(:empty)`` skips the chip."""
    html = _render(tid, accent=True, kicker="")
    if 'data-slot="kicker"' in html:
        assert re.search(r'data-slot="kicker">\s*</', html) and not re.search(
            r'data-slot="kicker">\s*[^<\s]', html
        )


# ---------------------------------------------------------------------------
# 3. Accent-less output has no trace of the accent; accent output has it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tid", _ids())
@pytest.mark.parametrize("ground", ["white", "black"])
def test_accentless_render_has_no_accent_trace(tid, ground):
    assert "color-accent" not in _render(tid, accent=False, ground=ground)
    assert "has_accent" not in _render(tid, accent=False, ground=ground)


@pytest.mark.parametrize("tid", _ids())
def test_accent_render_actually_uses_the_accent(tid):
    assert "var(--color-accent" in _render(tid, accent=True)


# ---------------------------------------------------------------------------
# 4. Display / headline weight is token-driven
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tid", _ids())
def test_display_weight_reads_the_token(tid):
    if tid in DISPLAY_WEIGHT_EXEMPT:
        pytest.skip("serif-voice quote headline keeps its fixed weight by design")
    assert "var(--font-weight-display" in _source(tid)
    # a hard-coded 700 must not survive on the headline any more
    for m in re.finditer(r"\.headline\s*\{([^{}]*)\}", _source(tid)):
        assert not re.search(r"font-weight\s*:\s*700\b", m.group(1)), (
            f"{tid}: .headline still hard-codes weight 700"
        )


# ---------------------------------------------------------------------------
# 5. Accent blocks are self-contained: stripping them == the accent-less render
# ---------------------------------------------------------------------------


def _squash(html: str) -> str:
    """Collapse blank lines — Jinja block removal can leave one; it's invisible."""
    return re.sub(r"\n\s*\n", "\n", html)


@pytest.mark.parametrize("tid", _ids())
@pytest.mark.parametrize("ground", ["white", "black"])
def test_accentless_render_is_stable_and_block_free(tid, ground):
    entry = _catalog()[tid]
    w, h = DIMS[entry["family"]]
    ctx = build_template_context(
        dict(COPY), "WRITING", ground, FOOTER, w, h, False,
        seed="theming", family=entry["family"], di_config={},
    )
    first = render_template_file(entry["file"], ctx)
    assert first == render_template_file(entry["file"], ctx)  # deterministic

    # removing the accent blocks from the source changes nothing accent-less
    from app.services.templates import render_template_html

    stripped = _strip_accent_blocks(_source(tid))
    assert _squash(render_template_html(stripped, ctx)) == _squash(first)

    # and switching the accent on does change the output
    ctx_on = dict(ctx, has_accent=True)
    assert render_template_file(entry["file"], ctx_on) != first
