"""The composer: concept → (subject, relation, field, framing) → scene.

Selection is deterministic for a given ``(seed, avoid)`` so a post re-renders
identically, while the caller can pass the compositions already used in the
set (``avoid_subjects`` / ``avoid_relations`` / ``avoid_fingerprints``) to get a
genuinely different combination. Nothing in here mutates global state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .catalog import (
    CONCEPT_NAMES,
    CONCEPTS,
    FIELDS,
    FRAMINGS,
    LEGACY_COMBOS,
    RELATIONS,
    SUBJECTS,
    concept_for,
)
from .fields import build_field
from .geom import Box, El, Frame, Group, Path
from .relations import fit_into, relation_extras, subject_target
from .subjects import Subject, build_subject

__all__ = [
    "ASPECTS",
    "Scene",
    "compose_cover_scene",
    "compose_scene",
    "resolve_concept",
    "select_combination",
]

ASPECTS: dict[str, tuple[int, int]] = {
    "square": (400, 400),
    "landscape": (480, 300),
    "portrait": (360, 450),
    "story": (300, 533),
    "wide": (520, 292),
}

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "limit": ("limit", "boundar", "asymptot", "comput", "complex", "constraint"),
    "growth": ("growth", "grow", "plant", "learn", "garden", "seed", "cultivat"),
    "system": ("system", "network", "structur", "architect", "interconnect"),
    "attention": ("attention", "focus", "observ", "watch", "signal", "notice"),
    "convergence": ("converg", "merge", "unite", "intersect", "together"),
    "choice": ("choice", "decision", "direction", "path", "crossroad", "navigat"),
    "scale": ("scale", "hierarch", "size", "measure"),
    "memory": ("memory", "memor", "history", "record", "archive", "read", "book"),
    "flow": ("flow", "movement", "motion", "stream", "current", "rhythm", "wave"),
    "craft": ("craft", "make", "build", "design", "hand", "practice", "tool"),
}


@dataclass
class Scene:
    concept: str
    subject: str
    relation: str
    field: str
    framing: str
    aspect: str
    frame: Frame
    els: list[El] = field(default_factory=list)
    subject_box: Box = field(default_factory=lambda: Box(0, 0, 0, 0))
    field_box: Box = field(default_factory=lambda: Box(0, 0, 0, 0))
    node: tuple[float, float] | None = None
    # Extra subject instances (sequence / scale-asymmetry), for diagnostics.
    copies: int = 1

    @property
    def fingerprint(self) -> str:
        return f"{self.subject}|{self.relation}|{self.field}"

    @property
    def safe(self) -> Box:
        return self.frame.safe_box

    def box(self) -> Box:
        out: Box | None = None
        for e in self.els:
            b = e.box()
            out = b if out is None else out.union(b)
        return out or Box(0, 0, 0, 0)

    def metrics(self) -> dict:
        b = self.box()
        safe = self.safe
        area = (b.w * b.h) / max(safe.w * safe.h, 1.0)
        return {
            "concept": self.concept,
            # ``archetype`` kept for callers of the old metrics contract.
            "archetype": self.subject,
            "subject": self.subject,
            "relation": self.relation,
            "field": self.field,
            "framing": self.framing,
            "fingerprint": self.fingerprint,
            "element_count": _count(self.els),
            "copies": self.copies,
            "box": b.as_dict(),
            "occupancy": round(min(area, 1.0), 3),
            "within_safe": b.x0 >= safe.x0 - 0.6 and b.y0 >= safe.y0 - 0.6
            and b.x1 <= safe.x1 + 0.6 and b.y1 <= safe.y1 + 0.6,
        }


def _count(els: list[El]) -> int:
    total = 0
    for e in els:
        total += 1
        if isinstance(e, Group):
            total += _count(e.els)
    return total


def resolve_concept(seed: str, concept: str = "", theme: str = "", title: str = "") -> str:
    value = (concept or "").strip().lower()
    if value in CONCEPTS:
        return value
    for candidate in (theme or "", title or ""):
        low = candidate.lower()
        if low.strip() in CONCEPTS:
            return low.strip()
        for name, words in _KEYWORDS.items():
            if any(word in low for word in words):
                return name
    rng = random.Random(f"concept|{seed or 'figure'}|{concept}|{theme}")
    return CONCEPT_NAMES[rng.randrange(len(CONCEPT_NAMES))]


def _rng_for(seed: str, *parts: object) -> random.Random:
    return random.Random("art|" + "|".join(str(p) for p in (seed, *parts)))


def select_combination(
    seed: str,
    concept: str,
    subject: str = "",
    relation: str = "",
    field: str = "",
    avoid_subjects: tuple[str, ...] = (),
    avoid_relations: tuple[str, ...] = (),
    avoid_fingerprints: tuple[str, ...] = (),
    avoid_pairs: tuple[str, ...] = (),
) -> tuple[str, str, str]:
    """Pick a (subject, relation, field) triple for a concept, avoiding repeats.

    ``avoid_pairs`` ("subject|relation") is the hard sequence rule — a post never
    shows the same subject in the same relation twice. Unused subjects and
    relations are preferred (soft), then relaxed rather than failing.
    """
    spec = CONCEPTS.get(concept) or CONCEPTS["system"]
    subs = spec["subjects"]
    if subject in SUBJECTS and subject != "portrait":
        subs = [subject]
    rels = [relation] if relation in RELATIONS else list(spec["relations"])
    flds = [field] if field in FIELDS else list(spec["fields"])

    combos = [(s, r, f) for s in subs for r in rels for f in flds]
    rng = _rng_for(seed, concept)
    rng.shuffle(combos)
    avoid_fp = set(avoid_fingerprints)
    avoid_pair = set(avoid_pairs) | {fp.rsplit("|", 1)[0] for fp in avoid_fp if fp.count("|") >= 2}

    def usable(combo: tuple[str, str, str]) -> bool:
        s, r, f = combo
        return f"{s}|{r}|{f}" not in avoid_fp and f"{s}|{r}" not in avoid_pair

    for s, r, f in combos:
        if usable((s, r, f)) and s not in avoid_subjects and r not in avoid_relations:
            return s, r, f
    for s, r, f in combos:
        if usable((s, r, f)):
            return s, r, f
    for s, r, f in combos:
        if f"{s}|{r}|{f}" not in avoid_fp:
            return s, r, f
    return combos[0]


def _pick_framing(seed: str, aspect: str, subject: str) -> str:
    if aspect == "portrait":
        pool = ("centered", "bottom-anchored", "bleed", "centered")
    elif aspect in ("landscape", "wide"):
        pool = ("left-third", "right-third", "centered", "left-third", "right-third")
    else:
        pool = ("centered", "bleed", "bottom-anchored", "left-third", "right-third")
    rng = _rng_for(seed, "frame", aspect, subject)
    return pool[rng.randrange(len(pool))]


def compose_scene(
    seed: str,
    ground: str = "white",
    concept: str = "",
    subject: str = "",
    relation: str = "",
    field: str = "",
    framing: str = "",
    aspect: str = "square",
    theme: str = "",
    title: str = "",
    avoid_subjects: tuple[str, ...] = (),
    avoid_relations: tuple[str, ...] = (),
    avoid_fingerprints: tuple[str, ...] = (),
    avoid_pairs: tuple[str, ...] = (),
) -> Scene:
    """Compose one scene. Pure: same inputs → byte-identical geometry."""
    aspect = aspect if aspect in ASPECTS else "square"
    frame = Frame(*ASPECTS[aspect])

    legacy = LEGACY_COMBOS.get((theme or "").strip().lower())
    if legacy and not subject:
        subject, relation, field = legacy
        concept = concept if concept in CONCEPTS else concept_for(subject)
    concept = resolve_concept(seed, concept, theme, title)

    subject, relation, field = select_combination(
        seed, concept, subject, relation, field,
        avoid_subjects, avoid_relations, avoid_fingerprints, avoid_pairs,
    )
    if framing not in FRAMINGS:
        framing = _pick_framing(seed, aspect, subject)

    rng = _rng_for(seed, "figure")
    spec = build_subject(subject, rng)
    return _assemble(
        concept=concept, subject=spec, relation=relation, field=field,
        framing=framing, aspect=aspect, frame=frame, seed=seed,
    )


def compose_cover_scene(
    seed: str,
    concept: str = "",
    theme: str = "",
    title: str = "",
    width: int = 1600,
    height: int = 900,
    placement: str = "center",
    subject: str = "",
    relation: str = "",
    field: str = "",
    avoid_fingerprints: tuple[str, ...] = (),
    avoid_pairs: tuple[str, ...] = (),
) -> Scene:
    """A cover: subject inside a generous safe frame, field bleeding to the edge."""
    frame = Frame(width=width, height=height, margin=0.12)
    aspect = "landscape"
    legacy = LEGACY_COMBOS.get((theme or "").strip().lower())
    if legacy and not subject:
        subject, relation, field = legacy
        concept = concept if concept in CONCEPTS else concept_for(subject)
    concept = resolve_concept(seed, concept, theme, title)
    subject, relation, field = select_combination(
        seed, concept, subject, relation, field,
        (), (), avoid_fingerprints, avoid_pairs,
    )
    rng = _rng_for(seed, "cover")
    spec = build_subject(subject, rng)
    safe = frame.safe_box
    cx = {"left": 0.34, "center": 0.52, "right": 0.68}.get(placement, 0.52)
    tw, th = safe.w * 0.5, safe.h * 0.72
    target = Box(
        safe.x0 + safe.w * cx - tw / 2,
        safe.y0 + safe.h * 0.5 - th / 2,
        safe.x0 + safe.w * cx + tw / 2,
        safe.y0 + safe.h * 0.5 + th / 2,
    )
    return _assemble(
        concept=concept, subject=spec, relation=relation, field=field,
        framing="cover", aspect=aspect, frame=frame, seed=seed,
        target_region=target, field_region=Box(0, 0, width, height),
        allow_bleed=True,
    )


def _assemble(
    *,
    concept: str,
    subject: Subject,
    relation: str,
    field: str,
    framing: str,
    aspect: str,
    frame: Frame,
    seed: str,
    target_region: Box | None = None,
    field_region: Box | None = None,
    allow_bleed: bool = False,
) -> Scene:
    safe = frame.safe_box
    target = target_region or subject_target(framing, safe, aspect)
    region = field_region or safe

    split = relation == "split"
    if split and target_region is None:
        region = Box(safe.x0, safe.y0, safe.x0 + safe.w * 0.44, safe.y1)
        target = Box(safe.x0 + safe.w * 0.50, safe.y0 + safe.h * 0.12,
                     safe.x1, safe.y1 - safe.h * 0.08)

    s, tx, ty = fit_into(subject.bounds, target)
    focus = (subject.focus[0] * s + tx, subject.focus[1] * s + ty)
    base = (subject.base[0] * s + tx, subject.base[1] * s + ty)
    subj_box = subject.bounds.scaled(s, tx, ty)

    # The field is built around the subject, so the relation is visible.
    field_hint = (
        min(max(focus[0], region.x0 + 4), region.x1 - 4),
        min(max(focus[1], region.y0 + 4), region.y1 - 4),
    )
    fld = build_field(field, _rng_for(seed, "field", field), region, field_hint)

    extras = relation_extras(
        relation, subj_box, safe, focus, base,
        divider_x=(region.x1 + 0.5) if split else None,
    )
    knock = [e for e in extras if _is_knockout(e)]
    overlay = [e for e in extras if not _is_knockout(e)]

    els: list[El] = list(fld.els) + knock
    els.append(Group(subject.els, s, tx, ty))
    copies = 1

    if relation == "sequence":
        echo_rng = _rng_for(seed, "sequence", subject.name)
        for k, scale in enumerate((0.5, 0.72)):
            w = target.w * 0.36
            h = target.h * 0.42
            cx = target.x0 + target.w * (0.2 + 0.30 * k) + echo_rng.uniform(-4, 4)
            cy = target.y1 - h / 2 - echo_rng.uniform(0, 6)
            es, etx, ety = fit_into(subject.bounds, Box(cx - w / 2, cy - h / 2,
                                                        cx + w / 2, cy + h / 2))
            els.append(Group(subject.els, es, etx, ety))
            copies += 1
    elif relation == "scale-asymmetry" and framing != "cover":
        w = target.w * 0.26
        h = target.h * 0.26
        ex = safe.x0 + safe.w * (0.16 if focus[0] > safe.cx else 0.84)
        ey = safe.y0 + safe.h * (0.20 if focus[1] > safe.cy else 0.80)
        es, etx, ety = fit_into(subject.bounds,
                                Box(ex - w / 2, ey - h / 2, ex + w / 2, ey + h / 2))
        els.append(Group(subject.els, es, etx, ety))
        copies += 1

    els.extend(overlay)

    scene = Scene(
        concept=concept,
        subject=subject.name,
        relation=relation,
        field=field,
        framing=framing,
        aspect=aspect,
        frame=frame,
        els=els,
        subject_box=subj_box,
        field_box=fld.box(),
        node=fld.node,
        copies=copies,
    )

    # Hard no-clip guarantee: if any element escaped the safe frame, fit the
    # whole scene uniformly. Authored geometry already sits inside, so this is
    # a safety net rather than the normal path.
    b = scene.box()
    if not allow_bleed and not (
        b.x0 >= safe.x0 - 0.6 and b.y0 >= safe.y0 - 0.6
        and b.x1 <= safe.x1 + 0.6 and b.y1 <= safe.y1 + 0.6
    ):
        fs, ftx, fty = frame.fit(b, safe)
        scene.els = [Group(scene.els, fs, ftx, fty)]
        scene.subject_box = scene.subject_box.scaled(fs, ftx, fty)
        scene.field_box = scene.field_box.scaled(fs, ftx, fty)
    return scene


def _is_knockout(el: El) -> bool:
    return isinstance(el, Path) and el.fill == "paper" and el.stroke is None
