"""Per-format recipe tests.

Slice 1 guarantee: a row written before recipes existed must synthesize a
recipe that reproduces the *old scattered derivation* exactly, so no post
changes behaviour and no migration is required.
"""

import json

from app.services.format_recipe import (
    FormatRecipe,
    legacy_view,
    parse_copy,
    read_recipe,
    recipe_json,
)

LEGACY_COPY = {
    "headline": "H",
    "subhead": "S",
    "body": "B",
    "tagline": "T",
    "extra": {"price": "9", "cta": ""},
}


def _legacy_entry(**over):
    """A pre-recipe per-format entry, exactly as generate.py used to write it."""
    entry = {
        "template_id": "square-editorial-stack",
        "copy": json.dumps(LEGACY_COPY),
        "editor": {
            "hidden": ["body"],
            "media_position": "left",
            "media_kind": "none",
            "media": {"kind": "none"},
            "design_system_id": "theorem",
            "revision": 4,
        },
    }
    entry.update(over)
    return entry


class TestSynthesis:
    def test_copies_every_legacy_field(self):
        r = read_recipe(_legacy_entry())
        assert r.template_id == "square-editorial-stack"
        assert r.headline == "H"
        assert r.subhead == "S"
        assert r.body == "B"
        assert r.tagline == "T"
        assert r.extra == {"price": "9", "cta": ""}
        assert r.hidden == ["body"]
        assert r.media_position == "left"
        assert r.design_system_id == "theorem"
        assert r.origin == "template"

    def test_ground_comes_from_the_brief(self):
        """This is the old `brief.get("ground", "white")` behaviour."""
        assert read_recipe(_legacy_entry(), brief={"ground": "black"}).ground == "black"
        assert read_recipe(_legacy_entry(), brief={}).ground == "white"

    def test_invalid_brief_ground_falls_back_to_white(self):
        """Matches the old `if ground not in (...): ground = "white"` guard."""
        assert read_recipe(_legacy_entry(), brief={"ground": "neon"}).ground == "white"
        assert read_recipe(_legacy_entry(), brief={"ground": None}).ground == "white"

    def test_language_and_category_from_task_level(self):
        """Old: `source.get("style_language")` / `source.get("category") or brief`."""
        r = read_recipe(
            _legacy_entry(),
            source_data={"style_language": "dark-luxury", "category": "PROJECT"},
            brief={"category": "WRITING"},
        )
        assert r.style_language == "dark-luxury"
        # source wins over brief, as before.
        assert r.category == "PROJECT"

    def test_category_falls_back_to_the_brief(self):
        r = read_recipe(_legacy_entry(), source_data={}, brief={"category": "NOTE"})
        assert r.category == "NOTE"

    def test_designer_post_has_no_template_and_origin_designer(self):
        r = read_recipe(_legacy_entry(template_id=None))
        assert r.template_id == ""
        assert r.origin == "designer"

    def test_missing_or_corrupt_copy_does_not_raise(self):
        assert read_recipe(_legacy_entry(copy="")).headline == ""
        assert read_recipe(_legacy_entry(copy="{not json")).headline == ""
        assert read_recipe(_legacy_entry(copy=None)).headline == ""

    def test_flat_slots_drops_empties(self):
        r = read_recipe(_legacy_entry())
        assert r.flat_slots() == {
            "headline": "H",
            "subhead": "S",
            "body": "B",
            "tagline": "T",
            "extra.price": "9",  # empty cta is dropped
        }


class TestStoredRecipe:
    def test_a_stored_recipe_is_authoritative(self):
        """Once written, the recipe wins over the legacy keys."""
        stored = recipe_json(
            FormatRecipe(
                template_id="story-stack",
                ground="black",
                style_language="playful",
                category="LAUNCH",
                headline="From the recipe",
            )
        )
        r = read_recipe(
            # Legacy fields deliberately contradict the recipe.
            {"recipe": stored, **_legacy_entry()},
            source_data={"style_language": "swiss-editorial", "category": "WRITING"},
            brief={"ground": "white"},
        )
        assert r.template_id == "story-stack"
        assert r.ground == "black"
        assert r.style_language == "playful"
        assert r.category == "LAUNCH"
        assert r.headline == "From the recipe"

    def test_corrupt_stored_recipe_falls_back_instead_of_bricking(self):
        """A malformed recipe must not make the post unrenderable."""
        r = read_recipe(
            {"recipe": {"ground": "chartreuse", "version": "nope"}, **_legacy_entry()},
            brief={},
        )
        # Re-derived from legacy, not from the bad blob.
        assert r.ground == "white"
        assert r.template_id == "square-editorial-stack"

    def test_round_trips_through_json(self):
        original = FormatRecipe(
            origin="designer",
            template_id="t",
            ground="black",
            style_language="bold-modern",
            category="NOTE",
            headline="H",
            extra={"cta": "go"},
            hidden=["subhead"],
            media_position="top",
            media={"kind": "illustration", "seed": 7},
        )
        assert read_recipe({"recipe": recipe_json(original)}).model_dump() == (
            original.model_dump()
        )


class TestLegacyView:
    def test_reproduces_the_entry_shape_existing_consumers_read(self):
        """The Studio's EditorState, task result and retries read these keys."""
        legacy = legacy_view(read_recipe(_legacy_entry()))
        assert legacy["template_id"] == "square-editorial-stack"
        assert json.loads(legacy["copy"]) == LEGACY_COPY
        assert legacy["editor"]["hidden"] == ["body"]
        assert legacy["editor"]["media_position"] == "left"
        assert legacy["editor"]["design_system_id"] == "theorem"

    def test_none_template_serializes_as_null(self):
        """generate.py wrote `template_id: None` for a designer post."""
        legacy = legacy_view(read_recipe(_legacy_entry(template_id=None)))
        assert legacy["template_id"] is None


class TestParseCopy:
    def test_accepts_dict_and_json_string(self):
        assert parse_copy({"a": 1}) == {"a": 1}
        assert parse_copy('{"a": 1}') == {"a": 1}

    def test_rejects_garbage_quietly(self):
        assert parse_copy("[1,2]") == {}
        assert parse_copy("nope") == {}
        assert parse_copy(None) == {}
        assert parse_copy(7) == {}
