"""Curated DiceBear avatar style registry.

DiceBear ships ~50 styles (each a JSON definition inside the ``dicebear-styles``
package — fully offline, deterministic per seed). Only a curated subset fits the
strict Swiss monochrome editorial system and safe licenses:

  - CC0 / free-for-commercial only (13 CC BY 4.0 styles are excluded — they
    require attribution, which the pipeline does not add).
  - No text-based styles (``initials`` renders letters), no emoji-adjacent
    styles (``fun-emoji``), no micro-canvas styles (``identicon`` 5×5,
    ``pixel-art`` 16×16), no gradient-based styles (forbidden by the Swiss
    ``gradients: false`` rule): ``avataaars``, ``constellation``, ``planets``.

Each entry carries a short AI-facing description (so the illustration director
picks intentionally) and the set of pinnable parts (people styles only —
abstract styles have no meaningful parts and ignore pinning).

Part values are **derived from the live DiceBear ``OptionsDescriptor``** (not
hardcoded) so they never drift from what the style actually accepts. A generic
part key (``facial_hair``, ``hair``, ``expression``, ``accessory``) maps onto
each style's real ``<part>Variant`` option; ``compose_peep`` then pins it via
``<part>Variant=<value>&<part>Probability=100``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files

from dicebear import OptionsDescriptor, Style

# Generic part key → per-style DiceBear option name. The allowed values are
# resolved from OptionsDescriptor at import time.
_PART_OPTIONS: dict[str, dict[str, str]] = {
    "open-peeps": {
        "facial_hair": "facialHairVariant",
        "hair": "headVariant",
        "expression": "expressionVariant",
        "accessory": "accessoriesVariant",
    },
    "lorelei": {
        "facial_hair": "beardVariant",
        "hair": "hairVariant",
        "expression": "mouthVariant",
        "accessory": "glassesVariant",
    },
    "lorelei-neutral": {
        "hair": "hairVariant",
        "expression": "mouthVariant",
        "accessory": "glassesVariant",
    },
    "notionists": {
        "facial_hair": "beardVariant",
        "hair": "hairVariant",
        "expression": "mouthVariant",
        "accessory": "glassesVariant",
    },
    "notionists-neutral": {
        "hair": "hairVariant",
        "expression": "mouthVariant",
        "accessory": "glassesVariant",
    },
    "bottts": {
        "expression": "mouthVariant",
        "hair": "topVariant",
    },
    "bottts-neutral": {
        "expression": "mouthVariant",
        "hair": "topVariant",
    },
}


@dataclass(frozen=True)
class StyleInfo:
    id: str
    label: str
    license: str
    description: str
    family: str  # people | creature | face | abstract | landscape
    parts: dict[str, tuple[str, list[str]]] = field(default_factory=dict)


def _resolve_parts(style_id: str, option_map: dict[str, str]) -> dict[str, tuple[str, list[str]]]:
    """Map generic part keys → (option name, allowed values) from the live def."""
    if not option_map:
        return {}
    try:
        descriptor = OptionsDescriptor(Style.from_json(_load_style_raw(style_id))).to_json()
    except Exception:  # noqa: BLE001 — never break the whole registry
        return {}
    out: dict[str, tuple[str, list[str]]] = {}
    for key, opt in option_map.items():
        spec = descriptor.get(opt)
        if spec and spec.get("type") == "enum" and spec.get("values"):
            out[key] = (opt, list(spec["values"]))
    return out


_raw_cache: dict[str, str] = {}


def _load_style_raw(style_id: str) -> str:
    if style_id not in _raw_cache:
        _raw_cache[style_id] = files("dicebear_styles").joinpath(f"{style_id}.json").read_text("utf-8")
    return _raw_cache[style_id]


CURATED_STYLES: dict[str, StyleInfo] = {k: v for k, v in {
    # --- People ---
    "open-peeps": StyleInfo(
        id="open-peeps", label="Open Peeps", license="CC0 1.0", family="people",
        description="Naive hand-drawn half-body person (Pablo Stanley). Good for posts about people, work, communities.",
    ),
    "lorelei": StyleInfo(
        id="lorelei", label="Lorelei", license="CC0 1.0", family="people",
        description="Polished illustrated person with many hair/beard/glasses options. Editorial but friendly.",
    ),
    "lorelei-neutral": StyleInfo(
        id="lorelei-neutral", label="Lorelei Neutral", license="CC0 1.0", family="people",
        description="Lorelei in a single neutral style (no colour variation). Clean, minimal people.",
    ),
    "notionists": StyleInfo(
        id="notionists", label="Notionists", license="CC0 1.0", family="people",
        description="Modern editorial people with expressive gestures and outfits. Good for tech/business/explainer posts.",
    ),
    "notionists-neutral": StyleInfo(
        id="notionists-neutral", label="Notionists Neutral", license="CC0 1.0", family="people",
        description="Notionists in a single neutral style. Minimal modern people.",
    ),
    "bottts": StyleInfo(
        id="bottts", label="Bottts", license="Free for commercial use", family="people",
        description="Monochrome robot character. Good for AI, automation, developer topics.",
    ),
    "bottts-neutral": StyleInfo(
        id="bottts-neutral", label="Bottts Neutral", license="Free for commercial use", family="people",
        description="Bottts robot in a single neutral style. Minimal robot.",
    ),
    # --- Creatures ---
    "critters": StyleInfo(
        id="critters", label="Critters", license="CC0 1.0", family="creature",
        description="Whimsical abstract creature (body + eyes + mouth). Good for playful or metaphorical posts.",
    ),
    "sprouts": StyleInfo(
        id="sprouts", label="Sprouts", license="CC0 1.0", family="creature",
        description="Plant-in-a-pot creature with a face. Good for growth, sustainability, gardening metaphors.",
    ),
    # --- Faces ---
    "clay": StyleInfo(
        id="clay", label="Clay", license="CC0 1.0", family="face",
        description="Single 3D-clay-looking face. Neutral, good for mood/identity posts.",
    ),
    "moods": StyleInfo(
        id="moods", label="Moods", license="CC0 1.0", family="face",
        description="Single blobby expressive face. Good for emotion/feeling themes.",
    ),
    "pixelbot": StyleInfo(
        id="pixelbot", label="Pixelbot", license="CC0 1.0", family="face",
        description="Pixel-style robot face. Retro-tech, good for coding/AI/retro themes.",
    ),
    "initial-face": StyleInfo(
        id="initial-face", label="Initial Face", license="CC0 1.0", family="face",
        description="Minimal geometric face. Abstract, good for identity/placeholder-like art.",
    ),
    # --- Abstract / shapes ---
    "blobs": StyleInfo(
        id="blobs", label="Blobs", license="CC0 1.0", family="abstract",
        description="Organic blob composition. Swiss-friendly abstract art for almost any topic.",
    ),
    "rings": StyleInfo(
        id="rings", label="Rings", license="CC0 1.0", family="abstract",
        description="Concentric ring diagram. Good for cycles, orbits, layers.",
    ),
    "stripes": StyleInfo(
        id="stripes", label="Stripes", license="CC0 1.0", family="abstract",
        description="Vertical bar stripes. Strong geometric pattern for editorial headers.",
    ),
    "triangles": StyleInfo(
        id="triangles", label="Triangles", license="CC0 1.0", family="abstract",
        description="Triangle composition. Geometric, good for sharp/build themes.",
    ),
    "waves": StyleInfo(
        id="waves", label="Waves", license="CC0 1.0", family="abstract",
        description="Layered wave fields. Good for flow, growth, rhythm.",
    ),
    "shapes": StyleInfo(
        id="shapes", label="Shapes", license="CC0 1.0", family="abstract",
        description="Collage of geometric shapes. Clean Swiss-style abstract art.",
    ),
    "squircles": StyleInfo(
        id="squircles", label="Squircles", license="CC0 1.0", family="abstract",
        description="Stack of rounded-corner shapes. Soft geometric pattern.",
    ),
    "shape-grid": StyleInfo(
        id="shape-grid", label="Shape Grid", license="CC0 1.0", family="abstract",
        description="Grid of squares and circles. Structural, good for systems/data themes.",
    ),
    "loops": StyleInfo(
        id="loops", label="Loops", license="CC0 1.0", family="abstract",
        description="Tiled loop pattern. Repetitive pattern, good for rhythm/automation.",
    ),
    "disco": StyleInfo(
        id="disco", label="Disco", license="CC0 1.0", family="abstract",
        description="Pentagon and pattern tiles. Retro-geometric, good for celebration/energy.",
    ),
    "weave": StyleInfo(
        id="weave", label="Weave", license="CC0 1.0", family="abstract",
        description="Woven band pattern. Good for craft, integration, connection.",
    ),
    # --- Landscape ---
    "landscape": StyleInfo(
        id="landscape", label="Landscape", license="CC0 1.0", family="landscape",
        description="Hills, sun and scenery. Good for journey, distance, horizon, growth-over-time.",
    ),
}.items() if v is not None}

# Attach pinnable parts resolved from the live style definitions.
for _sid, _info in CURATED_STYLES.items():
    object.__setattr__(_info, "parts", _resolve_parts(_sid, _PART_OPTIONS.get(_sid, {})))

CURATED_STYLE_IDS: list[str] = sorted(CURATED_STYLES.keys())

# Styles that expose pinnable parts (people + robot styles).
PINNABLE_STYLES: set[str] = {s for s, info in CURATED_STYLES.items() if info.parts}


_style_cache: dict[str, Style] = {}


def load_style(style_id: str) -> Style:
    """Return a cached DiceBear Style for a curated style id."""
    style_id = style_id if style_id in CURATED_STYLES else "open-peeps"
    if style_id not in _style_cache:
        _style_cache[style_id] = Style.from_json(_load_style_raw(style_id))
    return _style_cache[style_id]


def list_style_values(style_id: str, part: str) -> list[str]:
    """Return the allowed values for a generic part on a style (empty if none)."""
    info = CURATED_STYLES.get(style_id)
    if info is None or part not in info.parts:
        return []
    return info.parts[part][1]


def style_parts(style_id: str) -> dict[str, list[str]]:
    """Generic part key → allowed values for a style (people styles only)."""
    info = CURATED_STYLES.get(style_id)
    if info is None:
        return {}
    return {key: values for key, (_opt, values) in info.parts.items()}
