"""The published artwork vocabulary.

One catalog feeds the LLM tool enum, the cover motif picker, the compose
illustration picker and the Studio. Nothing else declares these names — adding
a subject or a field here makes it available everywhere.

A concept is the semantic layer the director chooses ("this post is about
limits"); the composer expands it into concrete subject/relation/field choices.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Dimensions of the composition grammar
# --------------------------------------------------------------------------- #

SUBJECTS: dict[str, dict] = {
    "seed": {"label": "Seed and sprout", "concept": "growth"},
    "vessel": {"label": "Plant in a vessel", "concept": "growth"},
    "hand": {"label": "Hand carrying a form", "concept": "craft"},
    "book": {"label": "Open book", "concept": "memory"},
    "arch": {"label": "Nested arches", "concept": "scale"},
    "ladder": {"label": "Ladder with a missing rung", "concept": "choice"},
    "bridge": {"label": "Bridge and traveller", "concept": "choice"},
    "orbit": {"label": "Orbital system", "concept": "convergence"},
    "curve-boundary": {"label": "Curve approaching a limit", "concept": "limit"},
    "network": {"label": "Node network", "concept": "system"},
    "wave-train": {"label": "Wave train with a break", "concept": "flow"},
    "prism": {"label": "Prism splitting a beam", "concept": "attention"},
    "loom": {"label": "Loom and weave", "concept": "system"},
    "compass": {"label": "Compass", "concept": "choice"},
    "magnifier": {"label": "Magnifier over a field", "concept": "attention"},
    "tunnel": {"label": "Converging tunnel", "concept": "limit"},
    "stack": {"label": "Stacked plates", "concept": "scale"},
    "portrait": {"label": "Portrait (curated avatar)", "concept": "craft"},
}

RELATIONS: dict[str, dict] = {
    "occlude": {"label": "Breaks the field"},
    "intersect-at-node": {"label": "Meets the field at a point"},
    "cradle": {"label": "Carried by the field"},
    "emerge-from": {"label": "Grows out of the field"},
    "converge-to": {"label": "Field converges on it"},
    "frame": {"label": "Framed by rules"},
    "split": {"label": "Field and subject split"},
    "sequence": {"label": "Repeats and transforms"},
    "scale-asymmetry": {"label": "Large with a distant echo"},
}

FIELDS: dict[str, dict] = {
    "grid": {"label": "Grid"},
    "bands": {"label": "Bands"},
    "contour": {"label": "Contours"},
    "hatch": {"label": "Hatch"},
    "stipple": {"label": "Stipple"},
    "halftone": {"label": "Halftone"},
    "flow": {"label": "Flow lines"},
    "phyllotaxis": {"label": "Phyllotaxis"},
    "nodes": {"label": "Node field"},
    "rays": {"label": "Rays"},
    "waves": {"label": "Wave field"},
    "dot-matrix": {"label": "Dot matrix"},
}

FRAMINGS: dict[str, dict] = {
    "centered": {"label": "Centred figure"},
    "left-third": {"label": "Figure left"},
    "right-third": {"label": "Figure right"},
    "bottom-anchored": {"label": "Anchored to the base"},
    "bleed": {"label": "Large, grounded"},
}

# A concept expands into concrete candidates. The composer then varies within
# these sets by seed and by the diversity ledger.
CONCEPTS: dict[str, dict] = {
    "limit": {
        "label": "Limits and boundaries",
        "subjects": ["curve-boundary", "tunnel", "ladder", "arch", "stack"],
        "relations": ["intersect-at-node", "frame", "converge-to", "scale-asymmetry"],
        "fields": ["grid", "bands", "contour"],
    },
    "growth": {
        "label": "Growth and cultivation",
        "subjects": ["seed", "vessel", "arch", "bridge", "ladder"],
        "relations": ["emerge-from", "cradle", "frame", "scale-asymmetry"],
        "fields": ["contour", "hatch", "stipple"],
    },
    "system": {
        "label": "Systems and interconnection",
        "subjects": ["network", "loom", "stack", "tunnel", "compass"],
        "relations": ["intersect-at-node", "sequence", "frame", "split"],
        "fields": ["nodes", "dot-matrix", "grid"],
    },
    "attention": {
        "label": "Attention and focus",
        "subjects": ["magnifier", "prism", "compass", "orbit", "network"],
        "relations": ["occlude", "converge-to", "scale-asymmetry", "frame"],
        "fields": ["halftone", "rays", "phyllotaxis"],
    },
    "convergence": {
        "label": "Convergence",
        "subjects": ["network", "orbit", "prism", "tunnel", "loom"],
        "relations": ["converge-to", "intersect-at-node", "scale-asymmetry", "frame"],
        "fields": ["rays", "nodes", "flow"],
    },
    "choice": {
        "label": "Choice and direction",
        "subjects": ["bridge", "ladder", "compass", "arch", "tunnel"],
        "relations": ["split", "sequence", "frame", "cradle"],
        "fields": ["grid", "bands", "dot-matrix"],
    },
    "scale": {
        "label": "Scale and hierarchy",
        "subjects": ["tunnel", "stack", "orbit", "arch", "ladder"],
        "relations": ["scale-asymmetry", "frame", "sequence", "split"],
        "fields": ["dot-matrix", "contour", "grid"],
    },
    "memory": {
        "label": "Memory and record",
        "subjects": ["book", "loom", "stack", "vessel", "network"],
        "relations": ["frame", "occlude", "cradle", "split"],
        "fields": ["hatch", "halftone", "stipple"],
    },
    "flow": {
        "label": "Flow and movement",
        "subjects": ["wave-train", "vessel", "loom", "bridge", "seed"],
        "relations": ["frame", "split", "sequence", "cradle"],
        "fields": ["flow", "waves", "phyllotaxis"],
    },
    "craft": {
        "label": "Craft and making",
        "subjects": ["hand", "vessel", "book", "seed", "compass"],
        "relations": ["cradle", "scale-asymmetry", "occlude", "frame"],
        "fields": ["contour", "stipple", "hatch"],
    },
}

CONCEPT_NAMES = tuple(CONCEPTS)

# --------------------------------------------------------------------------- #
# Legacy ids → (subject, relation, field)
#
# Old cover motifs, old archetypes and old saved media entries keep resolving.
# --------------------------------------------------------------------------- #

LEGACY_COMBOS: dict[str, tuple[str, str, str]] = {
    "hand-balance": ("hand", "cradle", "contour"),
    "hand-seed": ("seed", "cradle", "hatch"),
    "botanical-grid": ("seed", "emerge-from", "grid"),
    "asymptote-grid": ("curve-boundary", "intersect-at-node", "grid"),
    "convergence": ("network", "converge-to", "rays"),
    "contour": ("orbit", "frame", "contour"),
    "open-book": ("book", "scale-asymmetry", "hatch"),
    "vessel-growth": ("vessel", "cradle", "stipple"),
    "orbit": ("orbit", "scale-asymmetry", "dot-matrix"),
    "wave-field": ("wave-train", "frame", "waves"),
    "carrier-sun": ("orbit", "frame", "rays"),
    "sun-left": ("orbit", "scale-asymmetry", "rays"),
    "carrier-spiral": ("tunnel", "frame", "contour"),
    "spiral-free": ("tunnel", "scale-asymmetry", "phyllotaxis"),
    "diptych": ("arch", "split", "bands"),
    "column": ("stack", "sequence", "bands"),
    "cross": ("compass", "intersect-at-node", "grid"),
    "horizon": ("bridge", "frame", "waves"),
    "bounded-field": ("network", "occlude", "dot-matrix"),
    "stack-blobs": ("stack", "sequence", "stipple"),
    "rings-field": ("orbit", "frame", "dot-matrix"),
    "burst": ("prism", "converge-to", "rays"),
    "burst-left": ("prism", "scale-asymmetry", "rays"),
    "starburst": ("prism", "converge-to", "rays"),
    "stem": ("seed", "emerge-from", "bands"),
    "waves": ("wave-train", "frame", "waves"),
    "dot-grid": ("network", "intersect-at-node", "dot-matrix"),
    "radial-strokes": ("magnifier", "converge-to", "rays"),
    "mountains": ("bridge", "frame", "bands"),
    "biohazard": ("compass", "intersect-at-node", "rays"),
    "corner-mark": ("arch", "frame", "grid"),
    "slash": ("loom", "split", "hatch"),
    "wedge": ("tunnel", "frame", "bands"),
    "circle-quad": ("orbit", "sequence", "dot-matrix"),
    "landscape-line": ("wave-train", "frame", "bands"),
    "double-wave": ("wave-train", "split", "waves"),
    "ring-dash": ("compass", "frame", "dot-matrix"),
    "two-dots": ("orbit", "scale-asymmetry", "stipple"),
    "vertical-stripes": ("loom", "split", "hatch"),
    "diagonal": ("ladder", "sequence", "bands"),
    "cloud": ("vessel", "cradle", "stipple"),
    "pinwheel": ("prism", "sequence", "rays"),
    "rhythm-bars": ("stack", "sequence", "bands"),
    "field-flow": ("wave-train", "frame", "flow"),
    "field-burst": ("prism", "converge-to", "rays"),
    "field-tiles": ("stack", "sequence", "grid"),
    "field-blobs": ("vessel", "scale-asymmetry", "contour"),
    "field-orbits": ("orbit", "frame", "phyllotaxis"),
    "field-waves": ("wave-train", "frame", "waves"),
    "field-hatch": ("book", "occlude", "hatch"),
    "field-stipple": ("seed", "scale-asymmetry", "stipple"),
    "field-mesh": ("curve-boundary", "intersect-at-node", "flow"),
    "field-contour": ("tunnel", "frame", "contour"),
    "field-nodes": ("network", "intersect-at-node", "nodes"),
    "field-cubes": ("stack", "sequence", "dot-matrix"),
    "field-scribble": ("loom", "split", "flow"),
    "field-halftone": ("magnifier", "occlude", "halftone"),
    "field-phyllo": ("seed", "cradle", "phyllotaxis"),
    "field-lissajous": ("wave-train", "frame", "phyllotaxis"),
    "field-rose": ("orbit", "frame", "phyllotaxis"),
    "field-superformula": ("arch", "frame", "contour"),
    "field-attractor": ("network", "converge-to", "nodes"),
    "field-interference": ("wave-train", "split", "waves"),
    "field-function_family": ("curve-boundary", "converge-to", "grid"),
    "field-synthesis": ("network", "frame", "grid"),
    "synthesis": ("network", "frame", "grid"),
}


def concept_for(subject: str) -> str:
    return (SUBJECTS.get(subject) or {}).get("concept", "system")


def label_for(name: str) -> str:
    for table in (SUBJECTS, RELATIONS, FIELDS, FRAMINGS, CONCEPTS):
        entry = table.get(name)
        if entry:
            return entry["label"]
    return name.replace("-", " ").replace("_", " ")


__all__ = [
    "CONCEPTS",
    "CONCEPT_NAMES",
    "FIELDS",
    "FRAMINGS",
    "LEGACY_COMBOS",
    "RELATIONS",
    "SUBJECTS",
    "concept_for",
    "label_for",
]
