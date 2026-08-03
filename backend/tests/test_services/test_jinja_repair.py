"""Template-author Jinja repair tests — malformed block-close recovery."""

from app.services.template_author import clean_html, repair_jinja


def test_repair_fused_block_close():
    """LLM wrote `{% endif %}` fused with the body `>` -> missing brace."""
    html = '<body {% if ground == "black" %}data-ground="black"{% endif %>>'
    fixed = repair_jinja(html)
    assert "{% endif %}" in fixed
    assert "{% endif %>" not in fixed


def test_repair_parses_after_fix():
    from jinja2 import Environment

    html = (
        '<body {% if ground == "black" %}data-ground="black"{% endif %>>'
        "{% if kicker %}<span>{{ kicker }}</span>{% endif %}"
    )
    fixed = repair_jinja(html)
    Environment().parse(fixed)  # should not raise


def test_repair_leaves_css_percent_greater_alone():
    """Legitimate CSS like `width: 100% > 50%` must be untouched."""
    html = "@media (min-width: 100%) { .a > .b { width: 50%; } }"
    assert repair_jinja(html) == html


def test_clean_html_runs_repair():
    html = "<!DOCTYPE html><body {% if ground == 'black' %}x{% endif %>>"
    assert "{% endif %}" in clean_html(html)


def test_repair_multiple_fused_closes():
    html = (
        "{% if a %}A{% endif %}>"
        "{% if b %}B{% endfor %}>"
    )
    fixed = repair_jinja(html)
    assert "{% endif %}" in fixed
    assert "{% endfor %}" in fixed
