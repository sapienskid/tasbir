"""SVG rendering: scene → markup, tokens only."""

from __future__ import annotations

from .compose import ASPECTS, Scene
from .geom import fmt

__all__ = ["palette", "render_scene", "scene_svg"]

# Neutral token roles the art is allowed to reference. No raw hex, ever.
_VARS = {
    "ink": {"white": "var(--color-text)", "black": "var(--color-text-inverted)"},
    "carrier": {"white": "var(--color-border)", "black": "var(--color-border-inverted)"},
    "mid": {"white": "var(--color-text-secondary)", "black": "var(--color-text-secondary)"},
    "paper": {"white": "var(--color-bg)", "black": "var(--color-bg-inverted)"},
}


def palette(ground: str = "white", use_accent: bool = False) -> dict:
    """Role → CSS variable. Accent is a single emphasis mark, never the subject."""
    ground = ground if ground in ("white", "black") else "white"
    pal = {role: values[ground] for role, values in _VARS.items()}
    pal["accent"] = "var(--color-accent)" if use_accent else pal["mid"]
    return pal


def scene_svg(scene: Scene, ground: str = "white", use_accent: bool = False,
              width: float | None = None, height: float | None = None,
              scale: float = 2.0) -> str:
    """Render a scene as a standalone ``<svg>`` element."""
    pal = palette(ground, use_accent)
    fw = width or scene.frame.width
    fh = height or scene.frame.height
    body = "".join(e.svg(pal) for e in scene.els)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(fw * scale)}" '
        f'height="{fmt(fh * scale)}" viewBox="0 0 {fmt(fw)} {fmt(fh)}" '
        'preserveAspectRatio="xMidYMid meet" role="img" aria-hidden="true">\n'
        f"  {body}\n"
        "</svg>"
    )


def render_scene(scene: Scene, ground: str = "white", use_accent: bool = False,
                 width: float | None = None, height: float | None = None,
                 scale: float = 2.0) -> str:
    """Convenience wrapper used by the pipeline (slot-sized 2× output)."""
    return scene_svg(scene, ground=ground, use_accent=use_accent,
                     width=width, height=height, scale=scale)


ASPECT_NAMES = tuple(ASPECTS)
