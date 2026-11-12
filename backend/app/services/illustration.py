"""Procedural illustration facade.

The drawing engine lives in :mod:`app.services.art` (concept → subject ×
relation × field × framing). This module keeps the public entry points the
pipeline, covers, templates and the Studio already call, so nothing downstream
needs to know the engine was replaced.
"""

from __future__ import annotations

import logging

from app.services.art import (
    LEGACY_COMBOS,
    Scene,
    compose_cover_scene,
    compose_scene,
    render_scene,
)
from app.services.art.catalog import SUBJECTS

log = logging.getLogger(__name__)

__all__ = [
    "ARCHETYPES",
    "ILLUSTRATION_TOOL",
    "compose_cover_scene",
    "compose_scene",
    "generate_figure_metrics",
    "generate_illustration_svg",
    "illustration_via_tool",
    "render_scene",
]

# Legacy catalog ids still resolve (old saved posts, cover motifs, media entries).
ARCHETYPES: dict[str, tuple[str, str, str]] = dict(LEGACY_COMBOS)

# Kept for callers that imported the old element model indirectly.
VIEW_W, VIEW_H = 400, 240


def generate_illustration_svg(
    seed: str,
    ground: str = "white",
    theme: str | None = None,
    view_box: str | None = None,
    use_accent: bool = False,
    aspect: str = "square",
) -> str:
    """Render one deterministic illustration.

    ``theme`` accepts a concept (``limit``, ``growth`` …), a subject
    (``seed``, ``network`` …), a legacy archetype id (``hand-balance`` …) or a
    free-text hint that is keyword-mapped to a concept.
    """
    scene = compose_scene(
        seed or "figure",
        ground,
        theme=theme or "",
        aspect=aspect,
    )
    return render_scene(scene, ground, use_accent)


def generate_figure_metrics(
    seed: str, ground: str, theme: str | None, aspect: str = "square"
) -> dict:
    """Structural metrics for a rendered figure (used as LLM tool feedback)."""
    scene = compose_scene(seed or "figure", ground, theme=theme or "", aspect=aspect)
    return scene.metrics()


def scene_for(
    seed: str,
    ground: str = "white",
    theme: str | None = None,
    aspect: str = "square",
) -> Scene:
    return compose_scene(seed or "figure", ground, theme=theme or "", aspect=aspect)


# ---------------------------------------------------------------------------
# LLM tool integration
# ---------------------------------------------------------------------------

# The unified ``illustrate`` tool (scene composition OR curated avatars) lives
# in services/tools/illustrator.py; alias it here for import stability.
from app.services.tools.illustrator import ILLUSTRATE_TOOL as ILLUSTRATION_TOOL  # noqa: E402

_DIRECTOR_SYSTEM = (
    "You are the illustration director for this design system. An illustration "
    "is OPTIONAL — add one only if it genuinely strengthens this post. If you "
    "decide one helps, call the illustrate tool once. Choose a CONCEPT that "
    "matches the post's argument: "
    + ", ".join(sorted(SUBJECTS[name]["concept"] for name in SUBJECTS))
    + ". Use a portrait style only for human-centred posts. Never request "
    "words/letters, emoji, or colour terms. Keep the emphasis under 60 characters. "
    "If no illustration helps, do NOT call any tool."
)


async def illustration_via_tool(
    agent_role: str = "designer",
    title: str = "",
    headline: str = "",
    category: str = "",
    ground: str = "white",
    seed: str = "",
) -> str:
    """Ask the LLM for a post illustration through the unified tool.

    Returns the figure SVG if the LLM decides to illustrate, or "" if it
    declines or the tool call fails.
    """
    from app.services.llm import call_llm_for_tool
    from app.services.tools.illustrator import run_illustrate

    user = (
        f"Title: {title or '(untitled)'}\n"
        f"Headline: {headline or '(none)'}\n"
        f"Category: {category or '(none)'}\n"
        f"Ground: {ground}"
    )
    try:
        args = await call_llm_for_tool(
            agent_role=agent_role,
            system_prompt=_DIRECTOR_SYSTEM,
            user_prompt=user,
            tool=ILLUSTRATION_TOOL,
            temperature=0.8,
            max_tokens=1024,
        )
        return run_illustrate(args, seed)
    except Exception as e:  # noqa: BLE001
        log.warning("[illustration] LLM tool call failed (%s) — no illustration", e)
        return ""
