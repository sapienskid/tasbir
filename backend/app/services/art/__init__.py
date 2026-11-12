"""One illustration engine: concept → scene → SVG.

Public surface used by the pipeline, covers and the Studio. The old separate
engines (procedural archetypes, editorial field motifs, generative scenes) are
folded into this package.
"""

from .catalog import (
    CONCEPT_NAMES,
    CONCEPTS,
    FIELDS,
    FRAMINGS,
    LEGACY_COMBOS,
    RELATIONS,
    SUBJECTS,
    label_for,
)
from .compose import (
    ASPECTS,
    Scene,
    compose_cover_scene,
    compose_scene,
    resolve_concept,
    select_combination,
)
from .render import palette, render_scene, scene_svg

__all__ = [
    "ASPECTS",
    "CONCEPTS",
    "CONCEPT_NAMES",
    "FIELDS",
    "FRAMINGS",
    "LEGACY_COMBOS",
    "RELATIONS",
    "SUBJECTS",
    "Scene",
    "compose_cover_scene",
    "compose_scene",
    "label_for",
    "palette",
    "render_scene",
    "resolve_concept",
    "scene_svg",
    "select_combination",
]
