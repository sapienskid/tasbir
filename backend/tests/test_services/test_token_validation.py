"""Token value sanitizing, CSS injection hardening, and the contrast guard."""

import pytest

from app.services import design_systems as ds_service
from app.services.tokens import (
    build_css_variable_block,
    contrast_ratio,
    enforce_text_contrast,
    inject_tokens_into_html,
    sanitize_token_value,
)
from tests.test_api.conftest import authed_client  # noqa: F401 — API fixture


@pytest.mark.parametrize(
    "var,value",
    [
        ("--color-bg", "#FFF"),
        ("--color-bg", "#ffffff80"),
        ("--color-accent", "#E63B2E"),
        ("--color-accent", "rgb(10, 20, 30)"),
        ("--color-accent", "rgba(0,0,0,0.5)"),
        ("--color-accent", "hsl(210deg 50% 40%)"),
        ("--color-border", "transparent"),
        ("--color-border", "rebeccapurple"),
        ("--font-display", "Space Grotesk, Inter, sans-serif"),
        ("--font-sans", "Inter, 'Helvetica Neue', Arial, sans-serif"),
        ("--radius-sm", "0"),
        ("--radius-md", "12px"),
        ("--space-lg", "1.5rem"),
        ("--shadow-md", "none"),
        ("--shadow-md", "0 12px 32px rgba(0,0,0,0.18)"),
        ("--shadow-md", "inset 0 1px 0 #FFFFFF, 0 2px 4px black"),
        ("--custom", "1"),
    ],
)
def test_sanitizer_accepts(var, value):
    assert sanitize_token_value(var, value) == value


@pytest.mark.parametrize(
    "var,value",
    [
        ("--color-accent", ""),
        ("--color-accent", "   "),
        ("--color-accent", "red}</style><script>alert(1)</script>"),
        ("--color-accent", "#GGG"),
        ("--color-accent", "rgb(a, b, c)"),
        ("--color-accent", "red; background: url(x)"),
        ("--font-display", "Inter; } body { display:none"),
        ("--font-display", "Inter</style>"),
        ("--radius-sm", "12px; color: red"),
        ("--radius-sm", "big"),
        ("--shadow-md", "0 0 4px url(evil)"),
        ("--shadow-md", "0 0 red)"),
        ("--custom", "a{b}"),
        ("--custom", "x /* y"),
        ("--custom", "expression(alert(1))"),
        ("--custom", "back\\slash"),
    ],
)
def test_sanitizer_rejects(var, value):
    assert sanitize_token_value(var, value) is None


def test_css_block_drops_breakout_value():
    css = build_css_variable_block(
        {"--color-bg": "#FFFFFF", "--color-accent": "red}</style>", "--color-x": ""}
    )
    assert "</style>" not in css
    assert "--color-accent" not in css
    assert "--color-x" not in css
    assert "--color-bg: #FFFFFF;" in css

    html = inject_tokens_into_html(
        "<html><head></head><body></body></html>",
        {"--color-accent": "red}</style><script>alert(1)</script>"},
    )
    assert "<script>" not in html


def test_validate_design_system_reports_invalid_values():
    issues = ds_service.validate_design_system(
        {"tokens": {"--color-accent": "", "--color-bg": "red}</style>"}}
    )
    assert len(issues) == 2
    assert all("invalid value" in i for i in issues)
    assert ds_service.validate_design_system({"tokens": {"--color-bg": "#FFFFFF"}}) == []


def test_contrast_guard_replaces_low_contrast_text():
    out = enforce_text_contrast(
        {
            "--color-bg": "#FFFFFF",
            "--color-text": "#DDDDDD",
            "--color-bg-inverted": "#101010",
            "--color-text-inverted": "#303030",
            "--color-text-secondary": "#EEEEEE",
        }
    )
    assert out["--color-text"] == "#000000"
    assert out["--color-text-inverted"] == "#FFFFFF"
    assert contrast_ratio(out["--color-text-secondary"], "#FFFFFF") >= 3.0
    assert out["--color-text-secondary"] != "#000000"  # mixed, not replaced


def test_contrast_guard_keeps_readable_brand_colors():
    tokens = {
        "--color-bg": "#FFF8F0",
        "--color-text": "#1A1A2E",
        "--color-bg-inverted": "#1A1A2E",
        "--color-text-inverted": "#FFF8F0",
        "--color-text-secondary": "#5C5C70",
    }
    assert enforce_text_contrast(tokens) == tokens


async def test_update_api_rejects_invalid_token_values(authed_client):  # noqa: F811
    headers = {"x-api-key": "test-key"}
    r = await authed_client.post(
        "/api/design-systems", headers=headers, json={"name": "Token Guard"}
    )
    assert r.status_code == 200
    dsid = r.json()["id"]

    r = await authed_client.put(
        f"/api/design-systems/{dsid}",
        headers=headers,
        json={"tokens": {"--color-accent": "red}</style><script>"}},
    )
    assert r.status_code == 422
    assert "--color-accent" in r.json()["detail"]

    # A blank value is treated as "unset" (dropped), not persisted as `--x: ;`.
    r = await authed_client.put(
        f"/api/design-systems/{dsid}",
        headers=headers,
        json={"tokens": {"--color-bg": "#FAFAFA", "--color-accent": ""}},
    )
    assert r.status_code == 200
    assert r.json()["tokens"] == {"--color-bg": "#FAFAFA"}


def test_system_import_rejects_unsafe_token_values():
    from app.services.system_export import SCHEMA_VERSION, TABLES, validate_payload

    payload = {"schema_version": SCHEMA_VERSION, **{t: [] for t in TABLES}}
    payload["design_systems"] = [
        {"id": "evil", "tokens": {"--color-bg": "red}</style><script>x()</script>"}},
        {"id": "ok", "tokens": {"--color-bg": "#FFFFFF"}},
    ]
    issues = validate_payload(payload)
    assert any("'evil'" in i and "--color-bg" in i for i in issues)
    assert not any("'ok'" in i for i in issues)
