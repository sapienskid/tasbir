"""Composer — fill a template with copy/media and finalize it for rendering.

Two jobs, no LLM anywhere:

- ``finalize_html`` is the single implementation of the post-design injection
  sequence (tokens → Google Fonts → KaTeX → keyed images → logo) that every
  render path used to repeat by hand (renderer node, verifier, rerender,
  template previews, DS preview, template author, chat precheck).
- ``fill_template`` / ``compose_slide`` turn a template + typed copy + a media
  choice into HTML. The AI template node and Manual Compose share
  ``fill_template``; ``compose_slide`` is the deterministic manual path
  (operator-chosen template, copy, and media — see ADR-0021).
"""

from __future__ import annotations

import logging
from collections import OrderedDict

from app.services.ds_context import DSContext

log = logging.getLogger(__name__)

_KATEX_MARKER = "cdn.jsdelivr.net/npm/katex"


def finalize_html(
    html: str,
    ctx: DSContext,
    images: list[dict] | None = None,
    *,
    katex: bool = True,
    grayscale: bool | None = None,
    logo: bool = True,
) -> str:
    """Inject tokens, fonts, KaTeX, keyed images, and the logo into ``html``.

    Args:
        html: The filled/designed HTML document.
        ctx: Design-system context (tokens, design instruction, logo).
        images: ``data-image-key`` payloads ({data, mime, alt}); None = none.
        katex: Inject the KaTeX CDN block (callers holding operator-edited
            HTML pass ``katex_missing(html)`` so it is never duplicated).
        grayscale: Photo treatment; None follows the design language.
        logo: Substitute ``data-logo`` markers (off for already-baked HTML).
    """
    from app.services.design_instruction import (
        build_google_fonts_link,
        inject_fonts_into_html,
        photo_grayscale,
        substitute_image_keys,
        substitute_logo,
    )
    from app.services.tokens import inject_katex_into_html, inject_tokens_into_html

    di = ctx.design_instruction or {}
    html = inject_tokens_into_html(html, ctx.tokens)
    html = inject_fonts_into_html(html, build_google_fonts_link(ctx.tokens, di))
    if katex:
        html = inject_katex_into_html(html)
    if images:
        html = substitute_image_keys(
            html, images, grayscale=photo_grayscale(di) if grayscale is None else grayscale
        )
    if logo:
        html = substitute_logo(html, ctx.logo)
    return html


def katex_missing(html: str) -> bool:
    """True when the document does not already carry the KaTeX CDN block."""
    return _KATEX_MARKER not in html


async def run_hard_checks(
    html: str, ctx: DSContext, width: int, height: int, category: str = ""
) -> list[str]:
    """Deterministic QC + DOM overflow + low-contrast — the no-LLM hard gate.

    Same checks the rerender endpoint has always run; the vision audit is
    never part of this.
    """
    from app.agents.orchestrator.nodes import quality_check
    from app.services import dom_extractor

    display_value = ctx.tokens.get("--font-display", "Space Grotesk, Inter, sans-serif")
    display_family = display_value.split(",")[0].strip()
    di = ctx.design_instruction or {}
    issues = quality_check._run_deterministic_checks(
        html, ctx.footer or {}, category, width, height, display_family,
        allow_emoji=bool((di.get("style") or {}).get("emoji")),
    )
    issues.extend(await dom_extractor.detect_overflow(html, width, height))
    issues.extend(await dom_extractor.detect_low_contrast(html, width, height))
    return issues


# ---------------------------------------------------------------------------
# Template filling
# ---------------------------------------------------------------------------


def fill_template(
    html: str,
    *,
    copy: dict,
    kicker: str,
    ground: str,
    footer: dict,
    width: int,
    height: int,
    has_image: bool,
    seed: str,
    family: str,
    logo: str = "",
    di_config: dict | None = None,
    illustration: str | None = None,
    slide_index: int = 0,
    slide_total: int = 0,
    media_position: str = "auto",
    hidden: list[str] | None = None,
    photo: dict | None = None,
    grayscale: bool = True,
) -> str:
    """Render a Jinja2 template with copy + decisions, then embed a photo.

    ``photo`` is ``{image, credit}`` (an auto/stock photo); it fills the first
    ``data-image-key`` slot with a credit overlay.
    """
    from app.services.templates import build_template_context, render_template_html

    context = build_template_context(
        copy,
        kicker,
        ground,
        footer,
        width,
        height,
        has_image,
        seed=seed,
        family=family,
        logo=logo,
        di_config=di_config or {},
        illustration=illustration,
        slide_index=slide_index,
        slide_total=slide_total,
        media_position=media_position,
        hidden=hidden,
    )
    rendered = render_template_html(html, context)
    if photo:
        from app.services.tools.photo import embed_photo_into_html

        rendered = embed_photo_into_html(
            rendered, photo["image"], photo.get("credit", ""), grayscale=grayscale
        )
    return rendered


# ---------------------------------------------------------------------------
# Manual compose (ADR-0021)
# ---------------------------------------------------------------------------

_COPY_KEYS = ("headline", "subhead", "body", "tagline")

# Small in-process cache of downloaded stock photos so re-previewing a slide
# (every keystroke in the composer) does not re-download the same image.
_PHOTO_CACHE: OrderedDict[str, dict] = OrderedDict()
_PHOTO_CACHE_BYTES = 8 * 1024 * 1024  # the API container runs in ~192 MB


async def fetch_photo(media: dict) -> dict | None:
    """SSRF-guarded download of an operator-picked stock photo (cached)."""
    from app.services.tools.photo import download_photo

    url = str(media.get("url") or "")
    if not url.startswith("https://"):
        return None
    if url in _PHOTO_CACHE:
        _PHOTO_CACHE.move_to_end(url)
        return _PHOTO_CACHE[url]
    image = await download_photo({"url": url, "photographer": media.get("photographer") or ""})
    if image:
        _PHOTO_CACHE[url] = image
        while (
            len(_PHOTO_CACHE) > 1
            and sum(len(v.get("data", "")) for v in _PHOTO_CACHE.values()) > _PHOTO_CACHE_BYTES
        ):
            _PHOTO_CACHE.popitem(last=False)
    return image


def render_illustration(style: str, seed: str, ground: str) -> str:
    """Procedural or DiceBear illustration markup (offline, deterministic per seed)."""
    from app.services.tools.illustrator import run_illustrate

    ground = ground if ground in ("white", "black") else "white"
    return run_illustrate({"style": style or "procedural", "ground": ground}, seed=seed or "figure")


def slide_copy(copy: dict | None) -> tuple[str, dict]:
    """SlideSpec copy → (kicker, template copy dict). Empty extras are dropped."""
    copy = copy or {}
    out = {k: str(copy.get(k) or "") for k in _COPY_KEYS}
    out["extra"] = {k: str(v) for k, v in (copy.get("extra") or {}).items() if v}
    out["badge"] = None
    return str(copy.get("kicker") or ""), out


async def compose_slide(
    ctx: DSContext,
    template,
    fmt_id: str,
    slide: dict,
    slide_index: int,
    slide_total: int,
    ground: str,
    issues: list[str] | None = None,
) -> str:
    """Fill + finalize one slide of a manual composition → render-ready HTML.

    ``template`` is a Template row or a ``template_to_dict`` dict; ``slide`` a
    SlideSpec dict (copy/hidden/media_position/media). ``slide_index`` is
    1-based. Media: ``upload`` fills the image slot, ``photo`` is downloaded
    (SSRF-guarded) and embedded with its credit, ``illustration`` renders the
    procedural/DiceBear figure; ``none`` keeps the template's deterministic
    illustration fallback. A kind the template cannot host (see
    ``templates.media_kinds``) is ignored. Non-fatal problems (e.g. a photo
    that failed to download) are appended to ``issues``. No LLM is involved.
    """
    from app.agents.orchestrator.nodes.renderer import inject_slide_counter
    from app.services.design_instruction import photo_grayscale
    from app.services.formats import get_format_info, is_carousel
    from app.services.sanitizer import sanitize_html
    from app.services.templates import format_family, media_kinds, template_to_dict

    entry = template if isinstance(template, dict) else template_to_dict(template)
    html = entry.get("html") or ""
    fmt = get_format_info(fmt_id)
    family = format_family(fmt_id)
    ground = ground if ground in ("white", "black") else "white"
    grayscale = photo_grayscale(ctx.design_instruction)
    carousel = is_carousel(fmt_id)
    index, total = (slide_index, slide_total) if carousel else (0, 0)

    kicker, copy = slide_copy(slide.get("copy"))
    hidden = slide.get("hidden")
    if hidden is None:
        hidden = entry.get("hidden_elements") or []
    media_position = slide.get("media_position") or "auto"
    if media_position == "auto":
        media_position = entry.get("media_position") or "auto"

    kinds = media_kinds(html)
    media = slide.get("media") or {"kind": "none"}
    kind = media.get("kind") or "none"
    seed = f"{copy['headline'] or entry.get('id', '')}|{fmt_id}"

    # A media kind the template cannot host is ignored (the slide renders as
    # if no media was chosen) — never an error.
    illustration: str | None = None
    images: list[dict] = []
    photo: dict | None = None
    has_image = False
    if kind in ("upload", "photo") and "image" in kinds:
        if kind == "upload":
            images = [
                {
                    "data": media.get("data") or "",
                    "mime": media.get("mime") or "image/png",
                    "alt": media.get("alt") or "",
                }
            ]
            has_image = True
        else:
            image = await fetch_photo(media)
            if image is not None:
                photo = {"image": image, "credit": str(media.get("credit") or "")}
                has_image = True
            elif issues is not None:
                issues.append("Stock photo could not be downloaded — rendered without it")
        if has_image:
            illustration = ""  # never a procedural figure on top of a real image
    elif kind == "illustration" and "illustration" in kinds:
        illustration = render_illustration(
            str(media.get("style") or "procedural"), str(media.get("seed") or seed), ground
        )
    elif kind != "none":
        log.info("[composer] %s cannot host %s media — ignored", entry.get("id"), kind)

    rendered = fill_template(
        html,
        copy=copy,
        kicker=kicker,
        ground=ground,
        footer=ctx.footer,
        width=fmt.width,
        height=fmt.height,
        has_image=has_image,
        seed=seed,
        family=family,
        logo=ctx.logo,
        di_config=ctx.design_instruction,
        illustration=illustration,
        slide_index=index,
        slide_total=total,
        media_position=media_position,
        hidden=hidden,
        photo=photo,
        grayscale=grayscale,
    )
    # Same defense-in-depth + injection order as the AI renderer node.
    rendered = sanitize_html(rendered, mode="strict")
    rendered = finalize_html(rendered, ctx, images, grayscale=grayscale)
    if carousel and total > 0:
        rendered = inject_slide_counter(rendered, index, total)
    return rendered


__all__ = [
    "compose_slide",
    "fetch_photo",
    "fill_template",
    "finalize_html",
    "katex_missing",
    "render_illustration",
    "run_hard_checks",
    "slide_copy",
]
