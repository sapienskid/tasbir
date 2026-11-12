"""Artwork-only covers: the shared composition engine, palette-mapped AI art."""

from __future__ import annotations

import base64
import binascii
import random
from html import escape
from typing import Literal

import httpx
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.services.art import (
    CONCEPTS,
    LEGACY_COMBOS,
    compose_cover_scene,
    render_scene,
    resolve_concept,
)
from app.services.art.catalog import label_for
from app.services.ds_context import DSContext
from app.services.tokens import build_css_variable_block, resolve_ground_vars
from app.services.uploads import validate_upload

COVER_WIDTH, COVER_HEIGHT = 1600, 900
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

# Published by /covers/meta, so the Studio doesn't maintain a second catalog.
# Concepts are the primary vocabulary; legacy motif ids keep resolving.
COVER_MOTIFS: dict[str, str] = {
    "auto": "From the article",
    "random": "Random composition",
    "field-synthesis": "Generative composition",
}
for _name, _spec in CONCEPTS.items():
    COVER_MOTIFS.setdefault(_name, _spec["label"])
for _legacy in LEGACY_COMBOS:
    COVER_MOTIFS.setdefault(_legacy, label_for(_legacy))

COVER_SIZES = [
    {"label": "Blog / newsletter · 16:9", "width": 1600, "height": 900},
    {"label": "Open Graph · 1200 × 630", "width": 1200, "height": 630},
    {"label": "Square · 1080 × 1080", "width": 1080, "height": 1080},
]


class CoverRequest(BaseModel):
    design_system_id: str = Field(default="default", min_length=1, max_length=64)
    title: str = Field(default="", max_length=300)
    content: str = Field(default="", max_length=20_000)
    theme: str = Field(default="", max_length=1000)
    engine: Literal["procedural", "ai"] = "procedural"
    motif: str = Field(default="field-synthesis", max_length=64)
    ground: Literal["white", "black"] = "white"
    placement: Literal["center", "left", "right"] = "center"
    texture: Literal["clean", "print"] = "print"
    variations: int = Field(default=3, ge=1, le=4)
    seed: str = Field(default="", max_length=128)
    width: int = Field(default=COVER_WIDTH, ge=256, le=2400)
    height: int = Field(default=COVER_HEIGHT, ge=256, le=2400)

    @field_validator("motif")
    @classmethod
    def validate_motif(cls, value: str) -> str:
        if value not in COVER_MOTIFS:
            raise ValueError("Unknown cover composition")
        return value


def cover_theme(request: CoverRequest, index: int) -> str:
    """Resolve the motif id for one variation.

    ``auto`` maps the article's language to a concept; ``random`` rotates the
    concept list; an explicit concept or legacy motif id is used verbatim. The
    composer then varies subject/relation/field by variation index.
    """
    if request.motif == "random":
        names = sorted(CONCEPTS)
        return names[random.Random(request.seed).randrange(len(names))]
    if request.motif != "auto":
        return request.motif
    return resolve_concept(
        f"{request.seed}:{index}", "", request.theme, request.title
    )


def image_prompt(request: CoverRequest, motif: str) -> str:
    """Models receive visual direction only; palette is applied after inference."""
    context = f"{request.title}. {request.theme}. {request.content[:600]}"[:1000]
    return (
        "Minimalist editorial illustration inspired by mid-century scientific textbook "
        "covers. One coherent visual metaphor, flat geometric shapes and expressive "
        "hand-drawn linework, generous negative space. "
        f"Subject direction: {COVER_MOTIFS[motif]}. Article context: {context}. "
        + (
            "Subtle risograph stippling and imperfect printed edges. "
            if request.texture == "print"
            else "Clean flat shapes, crisp untextured surface. "
        )
        + f"Keep the entire subject in the central 55% of the image with wide empty "
        f"margins for a landscape crop; visual weight toward the {request.placement}. "
        "A bold focal silhouette with substantial mid-gray filled areas and confident "
        "dark linework on a white background. Avoid hairline-only diagrams. Grayscale only. "
        "No typography, text, words, "
        "letters, numbers, logos, signatures, photography, glossy 3D, or neon lighting."
    )[:2048]


async def generate_cover_image(prompt: str) -> tuple[str, str]:
    """Call Workers AI once. No silent fallback or billable automatic retries."""
    settings = get_settings()
    if not settings.resolved_cf_account_id or not settings.resolved_cf_token:
        raise ValueError("Cloudflare account and Workers AI token are required for AI covers")
    headers = {"Authorization": f"Bearer {settings.resolved_cf_token}"}
    if settings.cf_gateway_id:
        headers["cf-aig-gateway-id"] = settings.cf_gateway_id
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.resolved_cf_account_id}/ai/run/{IMAGE_MODEL}"
    )
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, headers=headers, json={"prompt": prompt, "steps": 4})
        if response.is_error:
            raise ValueError(
                f"Cloudflare image generation returned HTTP {response.status_code}; "
                "check Workers AI access and available quota"
            )
        data = response.json()
    if data.get("success") is False:
        raise ValueError("Cloudflare image generation failed")
    encoded = (data.get("result") or {}).get("image")
    if not isinstance(encoded, str) or len(encoded) > settings.image_max_bytes * 2:
        raise ValueError("Cloudflare returned an invalid image")
    try:
        return validate_upload(base64.b64decode(encoded, validate=True))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Cloudflare returned an invalid image") from exc


def _palette_filter(variables: list[str], transparent_paper: bool = False) -> str:
    """Quantize luminance into DS colors using SVG, including arbitrary CSS colors.

    Values stay in CSS variables. The image model never receives brand tokens,
    and hue from its output cannot leak into the exported artwork.
    """
    pieces = [
        '<filter id="cover-palette" x="0" y="0" width="100%" height="100%" '
        'color-interpolation-filters="sRGB">',
        '<feColorMatrix in="SourceGraphic" type="matrix" '
        'values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  .2126 .7152 .0722 0 0" '
        'result="luminance"/>',
    ]
    for i, var in enumerate(variables):
        table = " ".join("1" if j == i else "0" for j in range(len(variables)))
        pieces.append(
            f'<feComponentTransfer in="luminance" result="mask-{i}">'
            f'<feFuncA type="discrete" tableValues="{table}"/></feComponentTransfer>'
            f'<feFlood style="flood-color:var({var})" result="color-{i}"/>'
            f'<feComposite in="color-{i}" in2="mask-{i}" operator="in" result="band-{i}"/>'
        )
    pieces.append(
        "<feMerge>"
        + "".join(
            f'<feMergeNode in="band-{i}"/>' for i in range(len(variables) - int(transparent_paper))
        )
        + "</feMerge></filter>"
    )
    return "".join(pieces)


def build_cover_svg(
    request: CoverRequest,
    ctx: DSContext,
    index: int,
    image: tuple[str, str] | None = None,
) -> str:
    roles = resolve_ground_vars(request.ground, ctx.tokens, ctx.token_roles)
    css = build_css_variable_block(ctx.tokens)
    motif = cover_theme(request, index)
    background = roles["background"]
    ink = roles["text"]
    width, height = request.width, request.height
    # Map the shared drawing engine's conventional variables to custom DS roles.
    suffix = "-inverted" if request.ground == "black" else ""
    aliases = (
        f"--color-bg{suffix}:var({background});" if background != f"--color-bg{suffix}" else ""
    ) + (f"--color-text{suffix}:var({ink});" if ink != f"--color-text{suffix}" else "")
    border = roles["border"]
    if border != f"--color-border{suffix}":
        aliases += f"--color-border{suffix}:var({border});"
    defs = ""
    if image:
        palette = [ink, roles["secondary"], border, background]
        # An accent is used only when the selected design system defines one.
        if "--color-accent" in ctx.tokens:
            palette.insert(2, "--color-accent")
        has_accent = "--color-accent" in ctx.tokens
        defs = _palette_filter(palette, transparent_paper=has_accent)
        mime, encoded = image
        art = (
            f'<image width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice" '
            f'href="data:{escape(mime, quote=True)};base64,{encoded}" '
            'filter="url(#cover-palette)"/>'
        )
    elif motif.startswith("field-") or motif in CONCEPTS or motif in LEGACY_COMBOS:
        has_accent = "--color-accent" in ctx.tokens
        avoid: list[str] = []
        avoid_pairs: list[str] = []
        for prev in range(index):
            scene = compose_cover_scene(
                f"{request.seed}:{prev}",
                theme=cover_theme(request, prev),
                title=request.title,
                width=width,
                height=height,
                placement=request.placement,
                avoid_fingerprints=tuple(avoid),
                avoid_pairs=tuple(avoid_pairs),
            )
            avoid.append(scene.fingerprint)
            avoid_pairs.append(f"{scene.subject}|{scene.relation}")
        scene = compose_cover_scene(
            f"{request.seed}:{index}",
            theme=motif,
            title=request.title,
            width=width,
            height=height,
            placement=request.placement,
            avoid_fingerprints=tuple(avoid),
            avoid_pairs=tuple(avoid_pairs),
        )
        art = render_scene(
            scene, request.ground, has_accent, width=width, height=height, scale=1.0
        )
    else:
        scene = compose_cover_scene(
            f"{request.seed}:{index}",
            width=width,
            height=height,
            placement=request.placement,
        )
        art = render_scene(
            scene, request.ground, "--color-accent" in ctx.tokens,
            width=width, height=height, scale=1.0,
        )
    grain = ""
    if request.texture == "print" and not image:
        rng = random.Random(f"grain:{request.seed}:{index}")
        # Sparse ink specks stay away from the edge and use the same token palette.
        grain = (
            '<g opacity=".12">'
            + "".join(
                f'<circle cx="{rng.uniform(width * 0.05, width * 0.95):.1f}" '
                f'cy="{rng.uniform(height * 0.06, height * 0.94):.1f}" '
                f'r="{rng.uniform(0.4, 1.4):.1f}" style="fill:var({ink})"/>'
                for _ in range(240)
            )
            + "</g>"
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{request.width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Editorial cover illustration">'
        f"<style>{css}\nsvg{{{aliases}}}</style><defs>{defs}</defs>"
        f'<rect width="{width}" height="{height}" style="fill:var({background})"/>'
        f"{art}{grain}</svg>"
    )


def cover_html(svg: str, width: int = COVER_WIDTH, height: int = COVER_HEIGHT) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Cover</title><style>html,body{{margin:0;width:{width}px;height:{height}px;"
        "overflow:hidden}body>svg{display:block}</style></head><body>"
        f"{svg}</body></html>"
    )
