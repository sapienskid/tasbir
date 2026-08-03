"""Tests for the universal carousel slide counter injection."""

from app.agents.orchestrator.nodes.renderer import _inject_slide_counter

HTML = (
    "<!DOCTYPE html><html><head><style>:root{--color-text:#000}</style></head>"
    "<body data-ground=\"white\"><div class=\"sheet\">content</div></body></html>"
)


def _state(slide_id: str, total: int) -> dict:
    return {"slide_context": {slide_id: {"index": int(slide_id.rsplit("-", 1)[1]), "total": total}}}


def test_non_carousel_not_injected():
    out = _inject_slide_counter(HTML, {}, "linkedin-post")
    assert out == HTML
    assert "tasbir-slide-counter" not in out


def test_carousel_injected():
    out = _inject_slide_counter(HTML, _state("instagram-carousel-3", 5), "instagram-carousel-3")
    assert "tasbir-slide-counter" in out
    assert 'data-slot="counter">3/5' in out
    # no raw hex, no emoji; uses var() tokens only
    assert "#[0-9a-fA-F]" not in out
    assert "var(--color-text-secondary)" in out


def test_template_with_counter_skipped():
    html = HTML.replace("<body", '<body><span data-slot="counter">1/4</span>')
    out = _inject_slide_counter(html, _state("instagram-carousel-1", 4), "instagram-carousel-1")
    assert "tasbir-slide-counter" not in out  # not double-injected
    assert 'data-slot="counter">1/4' in out


def test_missing_total_skipped():
    out = _inject_slide_counter(HTML, {}, "instagram-carousel-1")
    assert "tasbir-slide-counter" not in out


def test_no_stray_body_angle_bracket():
    """The injected span must not leave a stray '>' text node that shifts
    layout (it would overflow the canvas by a line)."""
    out = _inject_slide_counter(HTML, _state("instagram-carousel-3", 5), "instagram-carousel-3")
    body = out.split("<body")[1]
    assert "</span>>" not in body, "stray '>' after the injected counter span"
    assert "<span class=\"tasbir-slide-counter\"" in body
    # the span is injected inside the body tag, before any other content
    assert body.index("<span class=\"tasbir-slide-counter\"") < body.index("<div")
