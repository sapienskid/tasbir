"""Brand Builder chain tests — design language, starters, atomicity (LLMs stubbed)."""

import json

import pytest

from app.services import brand_agent
from app.services.styles import build_style_rules_block

_STARTER_HTML = (
    "<!DOCTYPE html><html><head><style>body{width:{{ width }}px;"
    "height:{{ height }}px;background:var(--color-bg)}</style></head>"
    "<body><h1 data-slot=\"headline\">{{ headline }}</h1></body></html>"
)

_BASE_TOKENS = {
    "--color-bg": "#FFFFFF",
    "--color-bg-inverted": "#000000",
    "--color-text": "#111111",
    "--color-text-inverted": "#FFFFFF",
    "--color-text-secondary": "#6E6E6E",
    "--font-display": "Space Grotesk, Inter, sans-serif",
}


def _install_stubs(monkeypatch, name: str, tokens: dict, language: str = "",
                   fail_author_family: str = ""):
    authored: list[dict] = []

    async def fake_llm(*, agent_role, system_prompt, user_prompt, **_kw):
        if agent_role == "brand_vision":
            return json.dumps({
                "identity": {"name": name},
                "aesthetic": "clean",
                "ground": "white",
            })
        if agent_role == "brand_tokens":
            assert "AVAILABLE DESIGN LANGUAGES" in user_prompt
            assert "swiss-editorial" in user_prompt
            out = {
                "tokens": tokens,
                "token_roles": {},
                "design_instruction": {
                    "type_voice": {"display": "Loud brand headline voice."},
                    "do_dont": {"do": ["Brand-specific do"], "dont": []},
                },
            }
            if language:
                out["style_language"] = language
            return json.dumps(out)
        if agent_role == "brand_campaigns":
            return json.dumps({"campaigns": {"default": {
                "label": "Default", "tone": "bold", "ground": "white", "language": "x",
            }}})
        raise AssertionError(agent_role)

    async def fake_author(spec, ds, critique="", ground_hint="", source_html=""):
        if fail_author_family and spec["family"] == fail_author_family:
            raise RuntimeError("author exploded")
        authored.append(spec)
        return _STARTER_HTML

    async def fake_validate(html, family, ds, ground="white"):
        return {"ok": True, "issues": [], "critique": "", "rendered_html": html}

    monkeypatch.setattr(brand_agent, "call_llm", fake_llm)
    monkeypatch.setattr(brand_agent, "author_template_html", fake_author)
    monkeypatch.setattr(brand_agent, "validate_template_html", fake_validate)
    return authored


async def _load(ds_id):
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.db.repositories.templates import TemplateRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        ds = await DesignSystemRepository(session).get_by_id(ds_id)
        tpls = await TemplateRepository(session).list(ds_id, include_inactive=True)
    return ds, list(tpls)


async def test_accent_brand_gets_colorful_language_and_accent_rules(monkeypatch):
    from app.db.session import get_shared_session_factory

    tokens = {**_BASE_TOKENS, "--color-accent": "#E4572E", "--color-text": "#EEEEEE"}
    authored = _install_stubs(monkeypatch, "Accent Co", tokens, language="nonsense")
    pool = await get_shared_session_factory()
    result = await brand_agent.create_design_system_from_input(pool, {"name": "Accent Co"})

    ds, tpls = await _load(result["design_system_id"])
    di = ds.design_instruction
    assert ds.is_active
    assert di["style_language"] != "swiss-editorial"
    assert di["style"]["accent"] not in ("none", "", False)
    rules = build_style_rules_block(di)
    assert "var(--color-accent)" in rules
    assert "Accent: none" not in rules
    # Brand identity wins over the preset palette.
    assert ds.tokens["--color-accent"] == "#E4572E"
    # Low-contrast text token replaced (#EEEEEE on white is unreadable).
    assert ds.tokens["--color-text"] == "#000000"
    # Brand DI additions survive the language merge.
    assert di["type_voice"]["display"] == "Loud brand headline voice."
    assert "Brand-specific do" in di["do_dont"]["do"]

    families = {t.family for t in tpls}
    assert {"square", "landscape", "portrait", "story"} <= families
    # Variant b is a different layout from variant a.
    by_family: dict[str, list] = {}
    for spec in authored:
        by_family.setdefault(spec["family"], []).append(spec["regions"])
    assert by_family["square"][0] != by_family["square"][1]
    assert by_family["landscape"][0] != by_family["landscape"][1]


async def test_monochrome_brand_stays_swiss_with_authored_portrait(monkeypatch):
    from app.db.session import get_shared_session_factory

    tokens = {**_BASE_TOKENS, "--color-accent": ""}
    authored = _install_stubs(monkeypatch, "Mono Co", tokens, language="vibrant-pop")
    pool = await get_shared_session_factory()
    result = await brand_agent.create_design_system_from_input(pool, {"name": "Mono Co"})

    ds, tpls = await _load(result["design_system_id"])
    assert ds.design_instruction["style_language"] == "swiss-editorial"
    assert ds.design_instruction["style"]["accent"] == "none"
    assert "--color-accent" not in ds.tokens  # empty value dropped
    # Missing core tokens filled from the language palette / defaults.
    assert ds.tokens["--color-border"]
    assert "Accent: none" in build_style_rules_block(ds.design_instruction)
    families = {t.family for t in tpls}
    assert {"portrait", "story"} <= families
    assert {s["family"] for s in authored} >= {"portrait", "story"}


async def test_failure_mid_chain_leaves_no_design_system(monkeypatch):
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.db.session import get_shared_session_factory

    _install_stubs(
        monkeypatch, "Broken Co", dict(_BASE_TOKENS), fail_author_family="landscape"
    )
    pool = await get_shared_session_factory()
    with pytest.raises(RuntimeError):
        await brand_agent.create_design_system_from_input(pool, {"name": "Broken Co"})

    ds, tpls = await _load("broken-co")
    assert ds is None
    assert tpls == []
    async with pool() as session:
        ids = [d.id for d in await DesignSystemRepository(session).list(include_inactive=True)]
    assert not any(i.startswith("broken-co") for i in ids)


def test_build_tokens_drops_invalid_and_maps_palette_roles():
    tokens = brand_agent._build_tokens(
        {}, {"tokens": {"--color-accent": "red}</style>", "--color-bg": "#FFF", "x": "#000"}}
    )
    assert tokens == {"--color-bg": "#FFF"}
    tokens = brand_agent._build_tokens(
        {"palette": [{"role": "bg_inverted", "hex": "#111111"}, {"role": "accent", "hex": ""}]},
        {},
    )
    assert tokens == {"--color-bg-inverted": "#111111"}
