"""Bundled brand design systems (Fundaments.work, Theorem) — data + seeding."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.templates import TemplateRepository
from app.services.design_instruction import build_google_fonts_link
from app.services.design_systems import logo_data_uri, validate_design_system
from app.services.seeding import (
    bundled_row_values,
    catalog_template_specs,
    load_bundled_specs,
    sync_bundled_design_systems,
)
from app.services.styles import build_style_rules_block
from app.services.templates import (
    build_template_context,
    design_language_has_accent,
    render_template_html,
)
from app.services.tokens import contrast_ratio, invalid_token_issues

IDS = ["fundaments", "theorem"]
SPECS = {s["id"]: s for s in load_bundled_specs()}


def _run_with_pool(fn):
    """Run ``fn(pool)`` against a fresh, isolated temp database."""

    async def _go():
        from app.models import Base

        db = Path(tempfile.mkdtemp(prefix="tasbir-bundled-")) / "t.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        pool = async_sessionmaker(engine, expire_on_commit=False)
        try:
            return await fn(pool)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# The data itself
# ---------------------------------------------------------------------------


def test_both_systems_are_bundled():
    assert sorted(SPECS) == IDS


@pytest.mark.parametrize("ds_id", IDS)
def test_row_values_are_valid(ds_id):
    values = bundled_row_values(SPECS[ds_id])
    assert validate_design_system(values) == []
    assert invalid_token_issues(values["tokens"]) == []
    assert values["categories"] and values["campaigns"]["default"]["ground"] in ("white", "black")


@pytest.mark.parametrize("ds_id", IDS)
def test_palette_is_readable_on_both_grounds(ds_id):
    t = bundled_row_values(SPECS[ds_id])["tokens"]
    # Primary ink on each ground.
    assert contrast_ratio(t["--color-text"], t["--color-bg"]) >= 7
    assert contrast_ratio(t["--color-text-inverted"], t["--color-bg-inverted"]) >= 7
    # One shared secondary colour must clear 3:1 on both.
    assert contrast_ratio(t["--color-text-secondary"], t["--color-bg"]) >= 3
    assert contrast_ratio(t["--color-text-secondary"], t["--color-bg-inverted"]) >= 3
    # Accent is only ever a fill behind ink text.
    assert contrast_ratio(t["--color-text"], t["--color-accent"]) >= 4.5


@pytest.mark.parametrize("ds_id,weight", [("fundaments", "600"), ("theorem", "300")])
def test_language_typography_and_accent(ds_id, weight):
    values = bundled_row_values(SPECS[ds_id])
    di, tokens = values["design_instruction"], values["tokens"]
    assert design_language_has_accent(di)
    assert "var(--color-accent)" in build_style_rules_block(di)
    assert tokens["--font-weight-display"] == weight
    assert di["type_scale"]["roles"]["headline"]["weight"] == int(weight)
    # The brand's structural rules survive under the language/brand overlay.
    assert di["type_scale"]["roles"]["headline"]["family"] == "display"
    link = build_google_fonts_link(tokens, di)
    assert "family=Inter" in link and "JetBrains+Mono" in link
    assert weight in link.split("Inter:wght@")[1].split("&")[0]


def test_fundaments_is_dark_native_theorem_is_paper():
    ground = {i: bundled_row_values(SPECS[i])["design_instruction"]["default_ground"] for i in IDS}
    assert ground == {"fundaments": "black", "theorem": "white"}


def test_logos_are_inline_svg():
    for ds_id in IDS:
        logo = bundled_row_values(SPECS[ds_id])["logo"]
        assert logo["mime"] == "image/svg+xml"

        class _DS:
            pass

        ds = _DS()
        ds.logo = logo
        assert logo_data_uri(ds).startswith("data:image/svg+xml;base64,")


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def test_sync_creates_systems_with_their_own_template_copies():
    async def go(pool):
        summary = await sync_bundled_design_systems(pool)
        async with pool() as s:
            out = {}
            for ds_id in IDS:
                ds = await DesignSystemRepository(s).get_by_id(ds_id)
                rows = await TemplateRepository(s).list(ds_id, include_inactive=True)
                out[ds_id] = (ds, rows)
        return summary, out

    summary, out = _run_with_pool(go)
    assert sorted(summary["created"]) == IDS
    for ds_id, (ds, rows) in out.items():
        assert ds.source == "seed" and ds.is_active
        assert ds.logo and ds.logo["mime"] == "image/svg+xml"
        assert len(rows) == len(catalog_template_specs(ds_id, f"{ds_id}-"))
        assert all(r.id.startswith(f"{ds_id}-") and r.source == "seed" for r in rows)
        assert {r.family for r in rows} == {"square", "portrait", "story", "landscape"}
        names = {c["name"] for c in ds.categories}
        assert all(set(r.categories) <= names for r in rows)


def test_sync_is_idempotent():
    async def go(pool):
        await sync_bundled_design_systems(pool)
        return await sync_bundled_design_systems(pool)

    again = _run_with_pool(go)
    assert again["created"] == [] and again["updated"] == [] and again["templates"] == 0


def test_studio_edits_are_never_overwritten():
    async def go(pool):
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            repo = DesignSystemRepository(s)
            await repo.update(
                "fundaments", {"source": "manual", "tokens": {"--color-bg": "#010203"}}
            )
            tpl = TemplateRepository(s)
            await tpl.update(
                "fundaments-square-quote-card", {"source": "manual", "html": "<p>mine</p>"}
            )
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            ds = await DesignSystemRepository(s).get_by_id("fundaments")
            row = await TemplateRepository(s).get_by_id("fundaments-square-quote-card")
        return ds.tokens, row.html

    tokens, html = _run_with_pool(go)
    assert tokens == {"--color-bg": "#010203"}
    assert html == "<p>mine</p>"


def test_untouched_seed_rows_are_refreshed_from_the_files():
    async def go(pool):
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            await DesignSystemRepository(s).update("theorem", {"tokens": {"--color-bg": "#010203"}})
        summary = await sync_bundled_design_systems(pool)
        async with pool() as s:
            ds = await DesignSystemRepository(s).get_by_id("theorem")
        return summary, ds.tokens["--color-bg"]

    summary, bg = _run_with_pool(go)
    assert summary["updated"] == ["theorem"]
    assert bg == "#FAFAFA"


def test_deleted_system_is_not_resurrected():
    async def go(pool):
        from app.services.settings import (
            get_runtime_settings,
            invalidate_runtime_settings,
            refresh_runtime_settings,
        )

        await sync_bundled_design_systems(pool)
        async with pool() as s:
            await DesignSystemRepository(s).delete_cascade("theorem")
        summary = await sync_bundled_design_systems(pool)
        async with pool() as s:
            gone = await DesignSystemRepository(s).get_by_id("theorem")
            kept = await DesignSystemRepository(s).get_by_id("fundaments")
        # The internal marker row must not surface as a Studio setting.
        await refresh_runtime_settings(pool)
        knobs = await get_runtime_settings()
        invalidate_runtime_settings()
        return summary, gone, kept, knobs

    summary, gone, kept, knobs = _run_with_pool(go)
    assert gone is None and kept is not None
    assert summary["created"] == []
    assert any("theorem" in s and "deleted" in s for s in summary["skipped"])
    assert not any(k.startswith("seed.") for k in knobs)


# ---------------------------------------------------------------------------
# The cloned templates render with each brand's design instruction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ds_id", IDS)
def test_every_cloned_template_renders_with_the_brand(ds_id):
    di = bundled_row_values(SPECS[ds_id])["design_instruction"]
    copy = {
        "headline": "Why small teams ship faster",
        "subhead": "Four lessons from a year of shipping",
        "body": "Every handoff is a queue. Remove the queue and the work moves.",
    }
    specs = catalog_template_specs(ds_id, f"{ds_id}-")
    assert len(specs) >= 16
    for spec in specs:
        for ground in spec["grounds"]:
            ctx = build_template_context(
                copy, "PROJECT", ground, {"left": "", "right": "fundaments.work"},
                1080, 1080 if spec["family"] != "landscape" else 566, False,
                seed="t", family=spec["family"], di_config=di,
            )
            assert ctx["has_accent"] is True
            html = render_template_html(spec["html"], ctx)
            assert "{{" not in html and "{%" not in html, spec["id"]


# ---------------------------------------------------------------------------
# Brand languages + per-ground logos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ds_id,name", [("fundaments", "Fundaments.work"), ("theorem", "Theorem")])
def test_each_brand_has_its_own_language(ds_id, name):
    from app.db.repositories.design_languages import DesignLanguageRepository
    from app.services.design_languages import get_language

    async def go(pool):
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            ds = await DesignSystemRepository(s).get_by_id(ds_id)
            row = await DesignLanguageRepository(s).get_by_id(ds_id)
            lang = await get_language(s, ds_id)
        return ds, row, lang

    ds, row, lang = _run_with_pool(go)
    # Not one of the old presets: a language named for the brand.
    assert ds.design_instruction["style_language"] == ds_id
    assert row.source == "bundled" and row.name == name and row.accent and not row.emoji
    assert lang.name == name and lang.di["do_dont"]["dont"] and lang.di["layout_archetypes"]
    # The language's palette is the system's palette (one source of truth).
    for var, value in row.palette_tokens.items():
        assert ds.tokens[var] == value
    for var, value in row.accent_tokens.items():
        assert ds.tokens[var] == value


def test_language_edits_and_deletion_are_respected():
    from app.db.repositories.design_languages import DesignLanguageRepository

    async def go(pool):
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            repo = DesignLanguageRepository(s)
            await repo.update("fundaments", {"name": "Mine", "source": "manual"})
            await repo.delete("theorem") if hasattr(repo, "delete") else None
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            return (
                await DesignLanguageRepository(s).get_by_id("fundaments"),
                await DesignLanguageRepository(s).get_by_id("theorem"),
                await DesignSystemRepository(s).get_by_id("theorem"),
            )

    edited, deleted, ds = _run_with_pool(go)
    assert edited.name == "Mine"           # a Studio edit is never overwritten
    assert ds is not None                  # the system keeps working either way
    assert deleted is None or deleted.source == "bundled"


def test_logos_have_a_variant_per_ground():
    from app.services.design_systems import logo_data_uri, logo_variant_uris

    class _DS:
        pass

    for ds_id in IDS:
        ds = _DS()
        ds.logo = bundled_row_values(SPECS[ds_id])["logo"]
        white, black = logo_data_uri(ds, "white"), logo_data_uri(ds, "black")
        assert white.startswith("data:image/svg+xml") and black.startswith("data:image/svg+xml")
        assert white != black and set(logo_variant_uris(ds)) == {"white", "black"}
        assert logo_data_uri(ds) == logo_data_uri(ds, "black" if ds_id == "fundaments" else "white")


def test_pick_logo_and_baked_logo_survive_substitution():
    import base64

    from app.services.design_instruction import substitute_logo
    from app.services.ds_context import DSContext, pick_logo

    assert pick_logo("P", {"black": "B"}, "black") == "B"
    assert pick_logo("P", {"black": "B"}, "white") == "P"
    assert DSContext(ds_id="x", logo="P", logo_variants={"white": "W"}).logo_for("white") == "W"
    baked = "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode()
    html = f'<img class="brand-logo" data-logo src="{baked}" alt="">'
    # A template that already picked the ground's variant is never overwritten…
    assert substitute_logo(html, "data:image/png;base64,PRIMARY") == html
    # …while a bare placeholder (LLM designer output) still gets the logo.
    assert "PRIMARY" in substitute_logo('<div data-logo></div>', "data:image/png;base64,PRIMARY")


def test_upgrade_creates_the_language_for_an_existing_seed_system():
    """A DB seeded before brand languages existed gets them on the next start."""
    from app.db.repositories.design_languages import DesignLanguageRepository

    async def go(pool):
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            await DesignLanguageRepository(s).delete("fundaments")
        await sync_bundled_design_systems(pool)
        async with pool() as s:
            return await DesignLanguageRepository(s).get_by_id("fundaments")

    assert _run_with_pool(go).name == "Fundaments.work"
