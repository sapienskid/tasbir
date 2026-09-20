"""Composer tests — finalize_html parity, compose_slide per media kind, fields."""

import base64

import pytest

from app.services.composer import compose_slide, finalize_html, katex_missing
from app.services.ds_context import DSContext, apply_language_tokens
from app.services.templates import detect_fields, has_media, media_kinds
from app.services.tokens import DEFAULT_TOKEN_VALUES

_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode("ascii")
_LOGO = f"data:image/png;base64,{_PNG}"

_DESIGNED = (
    "<!DOCTYPE html><html><head><style>body{width:1080px;height:1080px}"
    ":root{--color-bg:#123456}</style></head><body>"
    '<div class="logo" data-logo></div><img data-image-key="0" alt="x"/>'
    '<span class="math">$x^2$</span></body></html>'
)

# A minimal template exercising every variable compose_slide fills.
_TEMPLATE_HTML = (
    "<!DOCTYPE html><html><head><style>body{width:{{ width }}px;height:{{ height }}px;"
    "font-family:var(--font-display)}</style></head>"
    '<body{% if ground == "black" %} data-ground="black"{% endif %}>'
    '<div data-slot="kicker">{{ kicker }}</div>'
    '<h1 data-slot="headline">{{ headline }}</h1>'
    '{% if subhead %}<p data-slot="subhead">{{ subhead }}</p>{% endif %}'
    '{% if extra.price %}<b class="price">{{ extra.price }}</b>{% endif %}'
    '{% if has_image %}<div class="media"><img data-image-key="0" alt=""/></div>{% endif %}'
    '<div class="art">{{ illustration | safe }}</div>'
    '<span data-slot="footer_right">{{ footer_right }}</span></body></html>'
)
_IMAGE_ONLY_HTML = _TEMPLATE_HTML.replace('<div class="art">{{ illustration | safe }}</div>', "")


def _template(html: str = _TEMPLATE_HTML, **kw) -> dict:
    return {
        "id": kw.get("id", "square-test"),
        "family": "square",
        "html": html,
        "hidden_elements": kw.get("hidden_elements", []),
        "media_position": kw.get("media_position", "auto"),
    }


def _ctx(**kw) -> DSContext:
    return DSContext(
        ds_id="default",
        tokens=dict(DEFAULT_TOKEN_VALUES),
        design_instruction=kw.get("di", {"photo": {"grayscale": True}}),
        footer={"left": "", "right": "@handle"},
        logo=kw.get("logo", ""),
    )


def _slide(media: dict | None = None, **copy) -> dict:
    return {
        "template_id": "square-test",
        "copy": {
            "kicker": copy.get("kicker", "NOTE"),
            "headline": copy.get("headline", "A headline"),
            "subhead": copy.get("subhead", "A subhead"),
            "body": "",
            "tagline": "",
            "extra": copy.get("extra", {}),
        },
        "hidden": copy.get("hidden"),
        "media_position": "auto",
        "media": media or {"kind": "none"},
    }


class TestFinalizeHtml:
    def test_parity_with_legacy_sequence(self):
        """Same output as the renderer's hand-written tokens→fonts→katex→images→logo."""
        from app.services.design_instruction import (
            build_google_fonts_link,
            inject_fonts_into_html,
            photo_grayscale,
            substitute_image_keys,
            substitute_logo,
        )
        from app.services.tokens import inject_katex_into_html, inject_tokens_into_html

        tokens = dict(DEFAULT_TOKEN_VALUES)
        di = {"photo": {"grayscale": False}, "type_scale": {"roles": {}}}
        images = [{"data": _PNG, "mime": "image/png", "alt": "a"}]

        legacy = inject_tokens_into_html(_DESIGNED, tokens)
        legacy = inject_fonts_into_html(legacy, build_google_fonts_link(tokens, di))
        legacy = inject_katex_into_html(legacy)
        legacy = substitute_image_keys(legacy, images, grayscale=photo_grayscale(di))
        legacy = substitute_logo(legacy, _LOGO)

        ctx = DSContext(ds_id="x", tokens=tokens, design_instruction=di, logo=_LOGO)
        assert finalize_html(_DESIGNED, ctx, images) == legacy

    def test_flags(self):
        ctx = _ctx(logo=_LOGO)
        out = finalize_html(_DESIGNED, ctx, katex=False, logo=False)
        assert katex_missing(out)
        assert _LOGO not in out
        assert ":root {" in out and "#123456" not in out  # designer :root stripped
        assert "fonts.googleapis.com/css2" in out

    def test_grayscale_follows_design_language_unless_overridden(self):
        images = [{"data": _PNG, "mime": "image/png", "alt": ""}]
        gray = finalize_html(_DESIGNED, _ctx(di={"photo": {"grayscale": True}}), images)
        color = finalize_html(_DESIGNED, _ctx(di={"photo": {"grayscale": False}}), images)
        forced = finalize_html(
            _DESIGNED, _ctx(di={"photo": {"grayscale": True}}), images, grayscale=False
        )
        assert "grayscale(1)" in gray
        assert "grayscale(1)" not in color
        assert "grayscale(1)" not in forced


class TestComposeSlide:
    async def test_none_keeps_deterministic_illustration_fallback(self):
        html = await compose_slide(
            _ctx(), _template(), "instagram-square", _slide(), 1, 1, "white"
        )
        assert "A headline" in html and "NOTE" in html
        assert "<svg" in html  # template's seeded procedural fallback
        assert 'data-image-key="0"' not in html  # has_image false → no slot
        assert ":root {" in html  # finalized
        assert "tasbir-slide-counter" not in html  # single post

    async def test_upload_fills_image_slot(self):
        media = {"kind": "upload", "data": _PNG, "mime": "image/png", "alt": "pic"}
        html = await compose_slide(
            _ctx(), _template(), "instagram-square", _slide(media), 1, 1, "white"
        )
        assert f"data:image/png;base64,{_PNG}" in html
        assert "grayscale(1)" in html  # monochrome DI → grayscale photo treatment
        assert "<svg" not in html  # no procedural figure on top of a real image

    async def test_photo_downloaded_and_credited(self, monkeypatch):
        from app.services import composer
        from app.services.tools import photo

        composer._PHOTO_CACHE.clear()
        calls = []

        async def fake_download(candidate):
            calls.append(candidate["url"])
            return {"data": _PNG, "mime": "image/jpeg", "alt": ""}

        monkeypatch.setattr(photo, "download_photo", fake_download)
        media = {
            "kind": "photo",
            "url": "https://images.example.com/a.jpg",
            "credit": "Photo by X on Pexels",
            "provider": "pexels",
            "photographer": "X",
            "license": "",
        }
        ctx = _ctx(di={"photo": {"grayscale": False}})
        html = await compose_slide(
            ctx, _template(), "instagram-square", _slide(media), 1, 1, "white"
        )
        assert "auto-photo" in html and "Photo by X on Pexels" in html
        assert "data:image/jpeg;base64," in html
        assert "grayscale(1)" not in html
        # Cached: a second preview does not re-download.
        await compose_slide(ctx, _template(), "instagram-square", _slide(media), 1, 1, "white")
        assert calls == ["https://images.example.com/a.jpg"]

    async def test_photo_download_failure_is_reported(self, monkeypatch):
        from app.services import composer
        from app.services.tools import photo

        composer._PHOTO_CACHE.clear()

        async def fake_download(candidate):
            return None

        monkeypatch.setattr(photo, "download_photo", fake_download)
        issues: list[str] = []
        media = {"kind": "photo", "url": "https://images.example.com/b.jpg"}
        html = await compose_slide(
            _ctx(), _template(), "instagram-square", _slide(media), 1, 1, "white", issues
        )
        assert "A headline" in html
        assert any("could not be downloaded" in i for i in issues)

    @pytest.mark.parametrize("style", ["procedural", "open-peeps"])
    async def test_illustration_styles(self, style):
        from app.services.composer import render_illustration

        media = {"kind": "illustration", "style": style, "seed": "abc"}
        html = await compose_slide(
            _ctx(), _template(), "instagram-square", _slide(media), 1, 1, "black"
        )
        assert 'data-ground="black"' in html
        assert "<svg" in html
        # Deterministic per seed.
        assert render_illustration(style, "abc", "black") == render_illustration(
            style, "abc", "black"
        )

    async def test_unhostable_media_is_ignored(self):
        media = {"kind": "illustration", "style": "procedural", "seed": "abc"}
        html = await compose_slide(
            _ctx(), _template(_IMAGE_ONLY_HTML), "instagram-square", _slide(media), 1, 1, "white"
        )
        assert "A headline" in html and "<svg" not in html

    async def test_hidden_override_and_template_default(self):
        tpl = _template(hidden_elements=["subhead"])
        default = await compose_slide(_ctx(), tpl, "instagram-square", _slide(), 1, 1, "white")
        assert "A subhead" not in default  # template default hides it
        shown = await compose_slide(
            _ctx(), tpl, "instagram-square", _slide(hidden=[]), 1, 1, "white"
        )
        assert "A subhead" in shown  # explicit [] overrides the default

    async def test_extras_and_logo(self):
        html = await compose_slide(
            _ctx(logo=_LOGO),
            _template(_TEMPLATE_HTML.replace("</body>", '<div data-logo></div></body>')),
            "instagram-square",
            _slide(extra={"price": "$9", "cta": ""}),
            1,
            1,
            "white",
        )
        assert '<b class="price">$9</b>' in html
        assert _LOGO in html

    async def test_carousel_slide_gets_counter(self):
        html = await compose_slide(
            _ctx(), _template(), "instagram-carousel-2", _slide(), 2, 3, "white"
        )
        assert "2/3" in html and "tasbir-slide-counter" in html


class TestTemplateFields:
    def test_detect_fields_scans_jinja_only(self):
        html = (
            "<style>body{}</style>{{ headline }}{% if extra.price %}{{ extra['cta'] }}"
            "{{ extra.get('date') }}{% endif %}{{ tagline | upper }}{{ other.body }}"
        )
        assert detect_fields(html) == [
            "headline", "tagline", "extra.price", "extra.cta", "extra.date"
        ]

    def test_media_kinds(self):
        assert media_kinds(_TEMPLATE_HTML) == ["image", "illustration"]
        assert media_kinds(_IMAGE_ONLY_HTML) == ["image"]
        assert media_kinds("<p>{{ headline }}</p>") == []
        assert has_media(_IMAGE_ONLY_HTML) and not has_media("<p>{{ headline }}</p>")


class TestDSContext:
    def test_apply_language_tokens_strips_accent_for_monochrome(self):
        from app.services.design_languages import LanguageDefinition

        tokens = {"--color-bg": "#FFF", "--color-accent": "#F00", "--font-sans": "Inter"}
        mono = LanguageDefinition(
            id="m", name="M", description="", palette_tokens={"--color-bg": "#EEE"}
        )
        out = apply_language_tokens(tokens, mono)
        assert out == {"--color-bg": "#EEE", "--font-sans": "Inter"}
        color = LanguageDefinition(
            id="c", name="C", description="", accent_tokens={"--color-accent": "#0F0"}
        )
        assert apply_language_tokens(tokens, color)["--color-accent"] == "#0F0"

    async def test_resolve_with_override_and_fallback(self):
        from app.services.ds_context import resolve_ds_context
        from app.services.styles import STYLE_PRESETS

        base = await resolve_ds_context(None, "default")
        assert base.ds_id == "default" and base.style_language == ""

        missing = await resolve_ds_context(None, "no-such-ds")
        assert missing.ds_id == "default"

        lang = next(k for k, v in STYLE_PRESETS.items() if v.get("accent_tokens"))
        styled = await resolve_ds_context(None, "default", lang)
        assert styled.style_language == lang
        assert styled.design_instruction["style_language"] == lang
        for var, value in STYLE_PRESETS[lang]["accent_tokens"].items():
            assert styled.tokens[var] == value

        unknown = await resolve_ds_context(None, "default", "no-such-language")
        assert unknown.style_language == "" and unknown.tokens == base.tokens
