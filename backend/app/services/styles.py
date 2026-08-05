"""Design-language presets — curated style bundles for social media design.

Phase 1 of the general-design-engine work: the pipeline no longer assumes a
Swiss monochrome editorial language. Each DesignSystem declares a
``style_language``; ``apply_style_preset`` merges that preset's rules into the
design-instruction dict, and ``build_style_rules_block`` renders a coherent
per-style rules block that every layer (designer, verifier, media-plan,
editor-chat) consumes instead of hardcoded monochrome text.

Grounds stay white/black for every preset — the ground machinery
(``resolve_ground``, ``data-ground`` attributes, ground token roles) is
unchanged. Styles differ in palette treatment (optional accent tokens),
decoration (radius/shadows/gradients), emoji policy, media policy, and type
mood. This keeps the change bounded while unlocking real visual breadth.
"""

from __future__ import annotations

import copy

# The canonical preset keys, in display order. ``swiss-editorial`` is the
# default and matches today's behaviour exactly.
STYLE_LANGUAGES: list[str] = [
    "swiss-editorial",
    "bold-modern",
    "dark-luxury",
    "vibrant-pop",
    "playful",
]

# Media policies a preset can declare. The media-plan director uses these to
# bias its per-slide choices.
MEDIA_POLICIES = ("photo-forward", "illustration-forward", "typographic")


def _do_dont(*do: str, dont: list[str]) -> dict:
    return {"do": list(do), "dont": dont}


STYLE_PRESETS: dict[str, dict] = {
    "swiss-editorial": {
        "label": "Swiss Editorial",
        "description": (
            "Monochrome, strict grid, three type voices, hairline rules, "
            "generous whitespace, grayscale photos."
        ),
        "emoji": False,
        "grayscale": True,
        "accent": False,
        "media_policy": "photo-forward",
        "accent_tokens": {},

        "palette_tokens": {
            "--color-bg": "#FFFFFF", "--color-bg-inverted": "#000000",
            "--color-text": "#000000", "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#6E6E6E", "--color-text-tertiary": "#B0B0B0",
            "--color-border": "#D9D9D9", "--color-border-inverted": "#2A2A2A",
            "--radius-sm": "0px", "--radius-md": "0px", "--shadow-md": "none",
        },        "palette_rules": (
            "pure black/white/gray only — NO hue of any kind; emphasis via "
            "weight and size, never color"
        ),
        "media_guide": (
            "PHOTO (strongly preferred) for concrete subjects, rendered "
            "grayscale; abstract procedural illustration only for abstract "
            "ideas; NONE for pure typography"
        ),
        "di": {
            "default_ground": "white",
            "style": {
                "name": "Swiss / International Typographic Style",
                "palette": "monochrome",
                "accent": "none",
                "max_weights_per_family": 2,
                "shadows": False,
                "border_radius": "0px",
                "illustrations": False,
                "icons": False,
                "emoji": False,
                "gradients": False,
            },
            "type_voice": {
                "display": (
                    "The signature display voice (var(--font-display)). Use it "
                    "ONLY for the headline. Big, tight, confident."
                ),
                "serif": (
                    "The editorial text voice (var(--font-serif)). It carries "
                    "the subhead and body copy."
                ),
                "body": (
                    "The quiet interface voice (var(--font-sans)) — category "
                    "label, metadata, handle."
                ),
            },
            "do_dont": _do_dont(
                "Left-align everything, always",
                "Use weight and size for hierarchy — never color",
                "THREE voices: display for headline; serif for "
                "subhead + body; sans for category, metadata, handle",
                "Constrain subhead/body copy to the measure",
                "Keep hairline rules exactly 1px",
                "Use generous whitespace — flexible space is intentional",
                dont=[
                    "No hue of any kind",
                    "No centering",
                    "No more than 2 weights per family",
                    "Never use the display face for body, subhead, category, "
                    "or metadata text",
                    "Never use the serif for headlines, category labels, or "
                    "metadata",
                    "No shadows, gradients, borders-with-radius, or any "
                    "softening effect",
                ],
            ),
            "layout_archetypes": {
                "editorial-stack": {
                    "description": (
                        "Category kicker, full-width display headline, then "
                        "subhead + body in a constrained measure column, footer "
                        "bottom-anchored. Headline-led with generous whitespace."
                    )
                },
                "split-editorial": {
                    "description": (
                        "Full-width display headline anchored top; subhead, "
                        "body, and/or math in a separate offset column beside "
                        "it. Asymmetric editorial composition."
                    )
                },
                "quiet-minimal": {
                    "description": (
                        "Reduced content: category, display headline, one short "
                        "subhead line, footer. Most of the canvas is intentional "
                        "whitespace; the headline floats high."
                    )
                },
            },
        },
    },
    "bold-modern": {
        "label": "Bold Modern",
        "description": (
            "High-contrast display type, generous scale, one strong accent "
            "allowed, clean shapes, full-color photos."
        ),
        "emoji": False,
        "grayscale": False,
        "accent": True,
        "media_policy": "photo-forward",
        "accent_tokens": {'--color-accent': '#E63B2E'},

        "palette_tokens": {
            "--color-bg": "#FFFFFF", "--color-bg-inverted": "#111111",
            "--color-text": "#111111", "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#555555", "--color-text-tertiary": "#9A9A9A",
            "--color-border": "#D0D0D0", "--color-border-inverted": "#2E2E2E",
            "--radius-sm": "0px", "--radius-md": "0px", "--shadow-md": "none",
        },        "palette_rules": (
            "high-contrast ink/paper/gray plus a single optional accent "
            "(var(--color-accent)) — the accent is used at most once per post"
        ),
        "media_guide": (
            "PHOTO (strongly preferred) for concrete subjects, rendered in "
            "full color; abstract procedural illustration only for abstract "
            "ideas; NONE for pure typography"
        ),
        "di": {
            "default_ground": "white",
            "style": {
                "name": "Bold Modern",
                "palette": "high-contrast",
                "accent": "accent",
                "max_weights_per_family": 2,
                "shadows": False,
                "border_radius": "0px",
                "illustrations": False,
                "icons": False,
                "emoji": False,
                "gradients": False,
            },
            "type_voice": {
                "display": (
                    "A large, confident display voice (var(--font-display)) "
                    "for the headline and key numerals. Tight tracking, "
                    "high contrast."
                ),
                "serif": (
                    "The editorial voice (var(--font-serif)) for subhead and "
                    "body when a measured, literary tone is needed."
                ),
                "body": (
                    "The interface voice (var(--font-sans)) for category, "
                    "metadata, and handle."
                ),
            },
            "do_dont": _do_dont(
                "Large display type that fills the canvas",
                "Use the accent token sparingly — one accent element max",
                "Strong weight contrast: bold headline vs quiet metadata",
                "Keep a clear margin grid; pick one alignment anchor",
                "Full-color photos, sharp rectangular crop",
                dont=[
                    "No more than one accent color per post",
                    "No busy multi-color palettes",
                    "No tiny body text",
                    "No gratuitous emoji",
                    "No excessive ornament or rounded cards",
                ],
            ),
            "layout_archetypes": {
                "bold-hero": {
                    "description": (
                        "One huge display headline owns most of the canvas; "
                        "category + handle small in a corner; photo optional "
                        "behind or beside."
                    )
                },
                "split-photo-text": {
                    "description": (
                        "A full-color photo on one half (full-bleed), large "
                        "display headline over or beside it, tight copy."
                    )
                },
                "index-stack": {
                    "description": (
                        "Kicker, oversized index numeral, headline mid-canvas, "
                        "quiet metadata row at the foot."
                    )
                },
            },
        },
    },
    "dark-luxury": {
        "label": "Dark Luxury",
        "description": (
            "Dark ground by default, a single refined accent (gold/brass), "
            "serif display, subtle depth, moody color photos."
        ),
        "emoji": False,
        "grayscale": False,
        "accent": True,
        "media_policy": "photo-forward",
        "accent_tokens": {'--color-accent': '#C9A227'},

        "palette_tokens": {
            "--color-bg": "#FFFFFF", "--color-bg-inverted": "#0E0E0E",
            "--color-text": "#111111", "--color-text-inverted": "#F2EDE4",
            "--color-text-secondary": "#8A8578", "--color-text-tertiary": "#6B675E",
            "--color-border": "#D8D3C8", "--color-border-inverted": "#3A362E",
            "--radius-sm": "0px", "--radius-md": "0px",
            "--shadow-md": "0 6px 24px rgba(0,0,0,0.25)",
        },        "palette_rules": (
            "dark ground by default; ink-on-light reserved for the inverted "
            "ground; a single luxury accent (var(--color-accent)) used "
            "sparingly; subtle shadows allowed"
        ),
        "media_guide": (
            "PHOTO (strongly preferred) for concrete subjects — moody, "
            "full-color photography; abstract procedural illustration only "
            "for abstract ideas; NONE for pure typography"
        ),
        "di": {
            "default_ground": "black",
            "style": {
                "name": "Dark Luxury",
                "palette": "dark + single accent",
                "accent": "accent",
                "max_weights_per_family": 2,
                "shadows": True,
                "border_radius": "0px",
                "illustrations": True,
                "icons": False,
                "emoji": False,
                "gradients": True,
            },
            "type_voice": {
                "display": (
                    "A refined, high-contrast display voice (var(--font-display)) "
                    "for the headline — elegant and quiet."
                ),
                "serif": (
                    "The editorial voice (var(--font-serif)) for subhead and "
                    "body — the literary reading voice."
                ),
                "body": (
                    "The interface voice (var(--font-sans)) for category, "
                    "metadata, and handle."
                ),
            },
            "do_dont": _do_dont(
                "Prefer the black ground; use the accent (gold/brass) "
                "sparingly for a single point of emphasis",
                "Subtle shadows and gradients allowed for depth",
                "A single composed illustration or moody photo is welcome — "
                "keep it toned to the palette",
                "Generous spacing — luxury is quiet",
                dont=[
                    "No bright, saturated multi-color palettes",
                    "No playful shapes or rounded cards",
                    "No gratuitous emoji",
                    "No busy layouts",
                ],
            ),
            "layout_archetypes": {
                "luxury-hero": {
                    "description": (
                        "Large headline on the dark ground, a single accent "
                        "element (rule or numeral), generous empty space, "
                        "small metadata row at the foot."
                    )
                },
                "gold-rule": {
                    "description": (
                        "A thin accent rule divides kicker from headline; "
                        "moody photo below or beside; quiet footer."
                    )
                },
                "quiet-pair": {
                    "description": (
                        "Headline + one subhead line centered on the dark "
                        "canvas, accent numeral as the only decoration."
                    )
                },
            },
        },
    },
    "vibrant-pop": {
        "label": "Vibrant Pop",
        "description": (
            "Vivid accent color, rounded shapes, gradients, playful, emoji "
            "allowed, illustration-forward."
        ),
        "emoji": True,
        "grayscale": False,
        "accent": True,
        "media_policy": "illustration-forward",
        "accent_tokens": {'--color-accent': '#FF2D78', '--color-accent-secondary': '#4DA6FF'},

        "palette_tokens": {
            "--color-bg": "#FFFFFF", "--color-bg-inverted": "#1A1A2E",
            "--color-text": "#131322", "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#5A5A6A", "--color-text-tertiary": "#9A9AA8",
            "--color-border": "#D8D8E0", "--color-border-inverted": "#33334A",
            "--radius-sm": "12px", "--radius-md": "24px",
            "--shadow-md": "0 12px 32px rgba(0,0,0,0.18)",
        },        "palette_rules": (
            "vivid — accents from the token palette (var(--color-accent), "
            "var(--color-accent-secondary)); the ground stays white/black; "
            "keep high contrast between text and ground"
        ),
        "media_guide": (
            "ILLUSTRATION (strongly preferred) — DiceBear figures or a "
            "procedural mark; PHOTO only when a subject is genuinely "
            "photographic; NONE for pure typography"
        ),
        "di": {
            "default_ground": "white",
            "style": {
                "name": "Vibrant Pop",
                "palette": "vivid",
                "accent": "accent",
                "max_weights_per_family": 2,
                "shadows": True,
                "border_radius": "24px",
                "illustrations": True,
                "icons": False,
                "emoji": True,
                "gradients": True,
            },
            "type_voice": {
                "display": (
                    "A bold, friendly display voice (var(--font-display)) for "
                    "the headline — energetic and confident."
                ),
                "serif": (
                    "The editorial voice (var(--font-serif)) for subhead and "
                    "body when a warmer, readable tone is needed."
                ),
                "body": (
                    "The interface voice (var(--font-sans)) for category, "
                    "metadata, and handle."
                ),
            },
            "do_dont": _do_dont(
                "Bold, friendly display type",
                "Use the accent tokens for energy — backgrounds, blocks, "
                "figures",
                "Rounded shapes and gradients are welcome",
                "Emoji allowed sparingly for tone",
                "Keep the composition legible and playful",
                dont=[
                    "No muddy low-contrast text/ground combos",
                    "No more than 2-3 colors drawn from the token palette",
                    "Never let a headline lose readability behind a busy "
                    "background",
                    "No cramped text",
                ],
            ),
            "layout_archetypes": {
                "pop-hero": {
                    "description": (
                        "Huge display headline over a rounded accent block, "
                        "figure beside or behind, sticker-like energy."
                    )
                },
                "rounded-stack": {
                    "description": (
                        "Category chip, headline, and body stacked inside "
                        "rounded panels on the ground; figure in a corner."
                    )
                },
                "figure-led": {
                    "description": (
                        "The illustration leads the canvas (large), with a "
                        "short headline + handle around it."
                    )
                },
            },
        },
    },
    "playful": {
        "label": "Playful",
        "description": (
            "Colorful, soft rounded shapes, big friendly type, emoji allowed, "
            "illustration-forward."
        ),
        "emoji": True,
        "grayscale": False,
        "accent": True,
        "media_policy": "illustration-forward",
        "accent_tokens": {'--color-accent': '#FF7A00', '--color-accent-secondary': '#5BD6A2'},

        "palette_tokens": {
            "--color-bg": "#FFFFFF", "--color-bg-inverted": "#26202E",
            "--color-text": "#26202E", "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#6A5A7A", "--color-text-tertiary": "#A99CB8",
            "--color-border": "#E0D8EA", "--color-border-inverted": "#3A3042",
            "--radius-sm": "16px", "--radius-md": "32px",
            "--shadow-md": "0 10px 28px rgba(0,0,0,0.16)",
        },        "palette_rules": (
            "friendly accents from the token palette (var(--color-accent), "
            "var(--color-accent-secondary)); ground stays white/black; warm, "
            "soft, approachable contrast"
        ),
        "media_guide": (
            "ILLUSTRATION (strongly preferred) — DiceBear figures or a "
            "procedural mark; PHOTO only for concrete photographic subjects; "
            "NONE for pure typography"
        ),
        "di": {
            "default_ground": "white",
            "style": {
                "name": "Playful",
                "palette": "friendly",
                "accent": "accent",
                "max_weights_per_family": 2,
                "shadows": True,
                "border_radius": "32px",
                "illustrations": True,
                "icons": False,
                "emoji": True,
                "gradients": True,
            },
            "type_voice": {
                "display": (
                    "A big, friendly display voice (var(--font-display)) for "
                    "the headline — approachable and warm."
                ),
                "serif": (
                    "The editorial voice (var(--font-serif)) for subhead and "
                    "body when a human, readable tone is needed."
                ),
                "body": (
                    "The interface voice (var(--font-sans)) for category, "
                    "metadata, and handle."
                ),
            },
            "do_dont": _do_dont(
                "Big, friendly display type",
                "Soft rounded shapes (cards, chips, buttons)",
                "Use accent tokens for warmth",
                "Emoji allowed for tone",
                "Keep it simple and approachable",
                dont=[
                    "No harsh, cluttered layouts",
                    "No more than 2-3 token colors per post",
                    "No low-contrast text",
                    "No corporate stiffness",
                ],
            ),
            "layout_archetypes": {
                "friendly-card": {
                    "description": (
                        "Headline + copy inside one big rounded panel, a "
                        "friendly figure at the foot."
                    )
                },
                "sticker-note": {
                    "description": (
                        "A bold headline with a rounded accent underline, "
                        "figure in a corner, short body."
                    )
                },
                "character-led": {
                    "description": (
                        "A character/DiceBear figure leads the canvas, "
                        "headline beside it, playful colors."
                    )
                },
            },
        },
    },
}


def style_labels() -> list[dict]:
    """Preset id + label + description for Studio/API consumption."""
    return [
        {
            "id": key,
            "label": preset["label"],
            "description": preset["description"],
            "emoji": preset["emoji"],
            "accent": preset["accent"],
            "grayscale": preset["grayscale"],
            "media_policy": preset["media_policy"],
            "accent_tokens": dict(preset.get("accent_tokens") or {}),
            "palette_tokens": dict(preset.get("palette_tokens") or {}),
        }
        for key, preset in STYLE_PRESETS.items()
    ]


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, recursing on dicts (override wins)."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


# The language-scoped fields a preset fully owns when applied.
_LANGUAGE_FIELDS = (
    "style",
    "type_voice",
    "do_dont",
    "layout_archetypes",
    "default_ground",
)
# Structural fields the user keeps if present, else filled from the preset.
_STRUCTURAL_FIELDS = (
    "type_scale",
    "spacing",
    "formats",
    "format_families",
    "footer",
    "images",
    "math",
)


def apply_style_preset(style_language: str, di: dict | None = None) -> dict:
    """Return a design-instruction dict configured for a style language.

    The preset owns the language fields (style, type_voice, do_dont,
    layout_archetypes, default_ground); structural fields (type_scale,
    spacing, formats, footer, ...) are preserved from ``di`` when present and
    only taken from the preset when absent. Unknown presets fall back to
    ``swiss-editorial``.
    """
    if style_language not in STYLE_PRESETS:
        style_language = "swiss-editorial"
    preset = STYLE_PRESETS[style_language]["di"]
    base = copy.deepcopy(di) if isinstance(di, dict) else {}
    result = copy.deepcopy(base)

    for key in _LANGUAGE_FIELDS:
        value = preset.get(key)
        if value is not None:
            result[key] = copy.deepcopy(value)

    # Media policy + grayscale live under ``photo`` (pipeline-readable).
    photo = {
        "grayscale": STYLE_PRESETS[style_language]["grayscale"],
        "media_policy": STYLE_PRESETS[style_language]["media_policy"],
    }
    if isinstance(result.get("photo"), dict):
        result["photo"].update(photo)
    else:
        result["photo"] = photo

    # Emoji flag is part of ``style`` (already set from the preset) — keep a
    # top-level mirror for simple reads.
    result["style_language"] = style_language
    for key in _STRUCTURAL_FIELDS:
        if not result.get(key) and preset.get(key) is not None:
            result[key] = copy.deepcopy(preset[key])
    return result


def _ground_text(allowed: list[str]) -> str:
    return ", ".join(allowed) if allowed else "white, black"


def build_style_rules_block(di: dict) -> str:
    """Render a coherent per-style rules block from a design-instruction dict.

    Replaces the hardcoded "STRICTLY MONOCHROME" palette text so designer and
    verifier prompts describe the DS's actual language. Reads ``style`` flags,
    ``style_language``, and ``photo`` — all with safe Swiss defaults so a
    stored DS missing the new fields keeps today's behaviour.
    """
    st = di.get("style") or {}
    language = di.get("style_language") or ""
    preset = STYLE_PRESETS.get(language)
    palette = st.get("palette") or "monochrome"
    accent = st.get("accent") or "none"
    policy = ((di.get("photo") or {}).get("media_policy")) or (
        preset.get("media_policy") if preset else "photo-forward"
    )
    grayscale = (di.get("photo") or {}).get("grayscale")
    if grayscale is None:
        grayscale = preset.get("grayscale") if preset else True

    lines = [
        "--- STYLE RULES (NON-NEGOTIABLE — follow exactly) ---",
    ]
    if preset:
        lines.append(f"  Design language: {preset['label']}")
    else:
        lines.append(f"  Design language: {language or 'custom'}")
    if preset:
        lines.append(f"  Palette: {preset['palette_rules']}")
    else:
        lines.append(f"  Palette: {palette} — brand token palette")
    lines.append(
        "  Allowed grounds: " + _ground_text(st.get("allowed_grounds") or ["white", "black"])
    )
    if accent not in ("none", "", False):
        lines.append(
            "  Accent: use var(--color-accent) / var(--color-accent-secondary) "
            "for emphasis ONLY — never introduce any other hue"
        )
    else:
        lines.append("  Accent: none — tonal/grayscale treatment via the token palette")
    lines.append(f"  Shadows: {'ALLOWED' if st.get('shadows') else 'FORBIDDEN'}")
    lines.append(f"  Border radius: {st.get('border_radius') or '0px'}")
    lines.append(f"  Gradients: {'ALLOWED' if st.get('gradients') else 'FORBIDDEN'}")
    lines.append(f"  Emoji: {'ALLOWED' if st.get('emoji') else 'FORBIDDEN'}")
    lines.append(
        "  Illustration/icons: "
        + ("ALLOWED in the designated slot" if st.get("illustrations") else "FORBIDDEN")
    )
    photo_note = "photos render grayscale" if grayscale else "photos render full color"
    lines.append(f"  Media policy: {policy} ({photo_note})")
    return "\n".join(lines)


def media_director_guidance(di: dict) -> str:
    """Per-style guidance for the media-plan director (one short paragraph)."""
    st = di.get("style") or {}
    language = di.get("style_language") or ""
    preset = STYLE_PRESETS.get(language)
    emoji_ok = bool(st.get("emoji"))
    grayscale = (di.get("photo") or {}).get("grayscale")
    if grayscale is None:
        grayscale = preset.get("grayscale") if preset else True

    if preset:
        guide = preset["media_guide"]
    else:
        guide = (
            "PHOTO for concrete visual subjects; abstract procedural "
            "illustration only for abstract ideas; NONE for pure typography"
        )
    extras = []
    if emoji_ok:
        extras.append("emoji are allowed in this style")
    extras.append("photos render grayscale" if grayscale else "photos render full color")
    return f"{guide}. ({'; '.join(extras)})" if extras else guide


def accent_tokens_for(style_language: str) -> dict:
    """Default accent token values a preset references (empty for monochrome)."""
    if style_language not in STYLE_PRESETS:
        return {}
    return dict(STYLE_PRESETS[style_language].get("accent_tokens") or {})


def palette_tokens_for(style_language: str) -> dict:
    """Core palette token values for a preset (bg/text/border/radius/shadow).

    Applying a design language overwrites the design system's core color
    tokens with these, so switching styles visibly changes the palette.
    Fonts are NOT included — they stay user-owned.
    """
    if style_language not in STYLE_PRESETS:
        return {}
    return dict(STYLE_PRESETS[style_language].get("palette_tokens") or {})


def normalize_design_instruction(di: dict) -> dict:
    """Fill style-language fields with Swiss defaults when a stored row lacks them.

    Older design-system rows (pre-Phase-1) have no ``style_language`` /
    ``photo`` keys. This fills them so pipeline consumers read a complete DI
    without changing the stored row.
    """
    out = copy.deepcopy(di or {})
    out.setdefault("style_language", "swiss-editorial")
    st = out.setdefault("style", {})
    st.setdefault("emoji", False)
    st.setdefault("palette", "monochrome")
    st.setdefault("accent", "none")
    photo = out.setdefault("photo", {})
    photo.setdefault("grayscale", True)
    photo.setdefault("media_policy", "photo-forward")
    return out


__all__ = [
    "STYLE_LANGUAGES",
    "STYLE_PRESETS",
    "MEDIA_POLICIES",
    "accent_tokens_for",
    "apply_style_preset",
    "build_style_rules_block",
    "media_director_guidance",
    "normalize_design_instruction",
    "palette_tokens_for",
    "style_labels",
]
