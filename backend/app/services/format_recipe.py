"""Per-format recipe — the self-contained description of one rendered post.

Every format of a task is fully described by a recipe: which template filled it,
which design system and design language rendered it, on which ground, with which
copy, element toggles and media. Re-rendering a format is then "apply the recipe",
with no reference to how the post was originally produced.

This exists because the values were previously scattered across three places:
``template_id`` / ``copy`` / ``editor`` on the per-format entry, but ``ground``
and ``style_language`` and ``category`` at *task* level (``strategic_brief`` and
``source_data``). That split is why a task's formats could not carry their own
ground or language, and why the editor had to re-derive them on every refill.

Reading is total and lazy: :func:`read_recipe` accepts an entry that predates
recipes and synthesizes one from the legacy fields plus the task-level values,
so existing rows keep rendering exactly as they did. The first write persists
the synthesized recipe and it becomes authoritative.

Not a DB table — the recipe lives inside the ``result`` JSON column on the
per-format entry.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

RECIPE_VERSION = 1

_COPY_FIELDS = ("headline", "subhead", "body", "tagline")


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def parse_copy(raw: Any) -> dict:
    """The per-format copy, stored as a JSON *string* on the legacy entry."""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


class FormatRecipe(BaseModel):
    """Everything needed to re-render one format, and nothing else."""

    version: int = RECIPE_VERSION
    # "template" = filled from the library; "designer" = freeform LLM output that
    # has no template yet (still convertible — set template_id to convert);
    # "compose" = Manual Compose.
    origin: Literal["template", "designer", "compose"] = "template"

    template_id: str = ""
    design_system_id: str = ""
    # "" means "the design system's own language" (the resolve_ds_context
    # sentinel) — not the same as naming swiss-editorial explicitly.
    style_language: str = ""
    ground: Literal["white", "black"] = "white"
    category: str = ""

    # Copy is flattened rather than nested under a `copy` key: these are already
    # the slot names the editor and templates speak (plus `extra.*`), so the
    # recipe has no translation layer. It also avoids shadowing BaseModel.copy.
    headline: str = ""
    subhead: str = ""
    body: str = ""
    tagline: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

    # None means "the template's own hidden_elements default", which is distinct
    # from an explicit empty list.
    hidden: list[str] | None = None
    media_position: str = "auto"
    media: dict | None = None

    def flat_slots(self) -> dict[str, str]:
        """The copy as flat slot names (``extra.price``) for the refill slot layer."""
        out: dict[str, str] = {}
        for key in _COPY_FIELDS:
            value = getattr(self, key, "")
            if value:
                out[key] = str(value)
        for key, value in _as_dict(self.extra).items():
            if value:
                out[f"extra.{key}"] = str(value)
        return out


def _normalize_ground(value: Any) -> Literal["white", "black"]:
    return value if value in ("white", "black") else "white"


def read_recipe(
    entry: dict,
    *,
    source_data: dict | None = None,
    brief: dict | None = None,
) -> FormatRecipe:
    """The recipe for a per-format entry, synthesizing one for legacy rows.

    The fallback reproduces the pre-recipe derivation exactly, so a row written
    before this module existed renders identically.
    """
    source = _as_dict(source_data)
    brief_d = _as_dict(brief)
    editor = _as_dict(entry.get("editor"))

    stored = entry.get("recipe")
    if isinstance(stored, dict):
        try:
            return FormatRecipe.model_validate(stored)
        except Exception as e:  # noqa: BLE001
            # A malformed recipe must not brick the post — fall through and
            # re-derive from the legacy fields.
            log.warning("[recipe] stored recipe for %r invalid, re-deriving: %s",
                        entry.get("html_path") or "?", e)

    template_id = str(entry.get("template_id") or "")
    copy = parse_copy(entry.get("copy"))
    return FormatRecipe(
        origin="template" if template_id else "designer",
        template_id=template_id,
        design_system_id=str(
            editor.get("design_system_id") or source.get("design_system_id") or ""
        ),
        style_language=str(source.get("style_language") or ""),
        ground=_normalize_ground(brief_d.get("ground", "white")),
        category=str(source.get("category") or brief_d.get("category") or ""),
        headline=str(copy.get("headline") or ""),
        subhead=str(copy.get("subhead") or ""),
        body=str(copy.get("body") or ""),
        tagline=str(copy.get("tagline") or ""),
        extra=dict(_as_dict(copy.get("extra"))),
        hidden=editor.get("hidden"),
        media_position=str(editor.get("media_position") or "auto"),
        media=editor.get("media"),
    )


def recipe_json(recipe: FormatRecipe) -> dict:
    """JSON-safe dict for persistence inside the result column."""
    return recipe.model_dump(mode="json")


def legacy_view(recipe: FormatRecipe) -> dict:
    """The pre-recipe entry fields, derived from the recipe.

    Slice 1 keeps these in sync on write so every existing consumer (the Studio's
    EditorState, the task result shape, media_credits, retries) is unaffected
    while the recipe is being introduced.
    """
    return {
        "template_id": recipe.template_id or None,
        "copy": json.dumps(
            {
                "headline": recipe.headline,
                "subhead": recipe.subhead,
                "body": recipe.body,
                "tagline": recipe.tagline,
                "extra": recipe.extra,
            },
            ensure_ascii=False,
        ),
        "editor": {
            "hidden": recipe.hidden,
            "media_position": recipe.media_position,
            "media_kind": (recipe.media or {}).get("kind") if recipe.media else None,
            "media": recipe.media,
            "design_system_id": recipe.design_system_id,
        },
    }


__all__ = [
    "RECIPE_VERSION",
    "FormatRecipe",
    "legacy_view",
    "parse_copy",
    "read_recipe",
    "recipe_json",
]
