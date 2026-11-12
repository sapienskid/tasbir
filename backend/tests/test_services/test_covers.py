"""Cover recipes, palette isolation, and the Workers AI response boundary."""

import base64
import re
from unittest.mock import AsyncMock
from xml.etree import ElementTree as ET

import httpx
import pytest

from app.services.covers import (
    CoverRequest,
    build_cover_svg,
    cover_theme,
    generate_cover_image,
    image_prompt,
)
from app.services.ds_context import DSContext
from app.services.illustration import generate_figure_metrics, generate_illustration_svg
from app.services.tokens import DEFAULT_TOKEN_VALUES

MOTIFS = [
    "hand-balance",
    "hand-seed",
    "botanical-grid",
    "asymptote-grid",
    "convergence",
    "contour",
    "open-book",
    "vessel-growth",
]


@pytest.mark.parametrize("motif", MOTIFS)
@pytest.mark.parametrize("ground", ["white", "black"])
def test_editorial_drawings_are_safe_and_seeded(motif, ground):
    svg = generate_illustration_svg("article-17", ground, motif)
    ET.fromstring(svg)
    assert svg == generate_illustration_svg("article-17", ground, motif)
    assert svg != generate_illustration_svg("article-18", ground, motif)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg)
    assert "<text" not in svg
    assert "None" not in svg
    metrics = generate_figure_metrics("article-17", ground, motif)
    assert metrics["archetype"] == motif
    assert metrics["within_safe"]


def test_cover_uses_selected_tokens_and_no_visible_text():
    tokens = {**DEFAULT_TOKEN_VALUES, "--color-bg": "#F3E9D2"}
    ctx = DSContext(ds_id="custom", tokens=tokens)
    request = CoverRequest(title="<script>bad()</script>", seed="repro", motif="hand-balance")
    svg = build_cover_svg(request, ctx, 0)
    ET.fromstring(svg)
    assert "#F3E9D2" in svg
    assert '<rect width="1600" height="900" style="fill:var(--color-bg)"' in svg
    assert "<script>" not in svg
    assert "<text" not in svg
    assert build_cover_svg(request, ctx, 0) == svg
    assert build_cover_svg(request, ctx, 1) != svg


def test_ai_palette_is_applied_after_generation():
    ctx = DSContext(
        ds_id="custom",
        tokens={
            **DEFAULT_TOKEN_VALUES,
            "--color-accent": "#D97757",
        },
    )
    request = CoverRequest(engine="ai", ground="black", title="Mathematical limits")
    prompt = image_prompt(request, "asymptote-grid")
    assert "#D97757" not in prompt
    assert "--color" not in prompt
    svg = build_cover_svg(request, ctx, 0, ("image/png", "aGVsbG8="))
    ET.fromstring(svg)
    assert 'filter="url(#cover-palette)"' in svg
    assert "var(--color-text-inverted)" in svg
    assert "flood-color:var(--color-accent)" in svg
    assert '<feFuncA type="discrete"' in svg


def test_auto_direction_is_related_and_operator_choice_wins():
    request = CoverRequest(title="The limits of computation")
    assert cover_theme(request, 0) == "asymptote-grid"
    assert cover_theme(request, 1) == "field-mesh"
    request.motif = "hand-seed"
    assert cover_theme(request, 0) == cover_theme(request, 1) == "hand-seed"
    assert len(image_prompt(CoverRequest(content="x" * 20_000), "contour")) <= 2048


@pytest.mark.parametrize(
    "status,body,message",
    [
        (403, {}, "HTTP 403"),
        (200, {"success": False}, "generation failed"),
        (200, {"result": {"image": "invalid-base64"}}, "invalid image"),
        (200, {"result": {"image": base64.b64encode(b"not an image").decode()}}, "invalid image"),
    ],
)
async def test_workers_ai_errors_are_clear(monkeypatch, status, body, message):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_account_id", "account")
    monkeypatch.setattr(settings, "cloudflare_ai_gateway_token", "token")
    response = httpx.Response(status, json=body, request=httpx.Request("POST", "https://test"))
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(ValueError, match=message):
        await generate_cover_image("test")
    assert post.await_count == 1


async def test_workers_ai_success_uses_gateway_and_sniffed_mime(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_account_id", "account")
    monkeypatch.setattr(settings, "cloudflare_ai_gateway_token", "token")
    monkeypatch.setattr(settings, "cf_gateway_id", "tasbir")
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()
    response = httpx.Response(200, json={"success": True, "result": {"image": encoded}})
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    assert await generate_cover_image("test") == ("image/png", encoded)
    assert post.call_args.kwargs["headers"]["cf-aig-gateway-id"] == "tasbir"


def test_default_lime_accent_has_consistent_rules():
    from pathlib import Path

    from app.services.design_instruction import load_design_instruction
    from app.services.styles import build_style_rules_block
    from app.services.tokens import load_tokens

    base = Path(__file__).resolve().parents[2] / "data" / "design_system"
    tokens = load_tokens(base / "tokens.yaml")
    di = load_design_instruction(base / "design-instruction.yaml")
    assert tokens["--color-accent"] == "#C6F432"
    assert di["style"]["accent"] == "accent"
    rules = build_style_rules_block(di)
    assert "var(--color-accent)" in rules
    assert "NO hue of any kind" not in rules
    assert "#C6F432" not in rules
    # Adding an accent to default must not silently recolor unrelated systems.
    assert "--color-accent" not in DEFAULT_TOKEN_VALUES
