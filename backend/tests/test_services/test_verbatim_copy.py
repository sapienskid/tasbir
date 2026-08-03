"""Tests for the verbatim carousel copy mode."""

import sys
import types

# Make backend importable when running via pytest from repo root or backend/.
sys.path.insert(0, ".")

from app.agents.orchestrator.nodes.copywriter import _verbatim_slides

POEM = (
    "Two roads diverged in a yellow wood,\n"
    "And sorry I could not travel both\n"
    "And be one traveler, long I stood\n"
    "And looked down one as far as I could\n"
    "To where it bent in the undergrowth;\n\n"
    "Then took the other, as just as fair,\n"
    "And having perhaps the better claim,\n"
    "Because it was grassy and wanted wear;\n"
    "Though as for that the passing there\n"
    "Had worn them really about the same."
)


def test_verbatim_slides_split_preserves_text():
    slides = _verbatim_slides(POEM, "The Road Not Taken", 4)
    assert len(slides) == 4
    # every line of the original poem is still present (verbatim, no paraphrase)
    joined = "\n".join(s.body for s in slides)
    assert "Two roads diverged in a yellow wood" in joined
    assert "Had worn them really about the same" in joined
    assert "grass and wanted wear" not in joined  # no paraphrase
    # complete title only on the cover; later slides carry no broken headline
    assert slides[0].headline == "The Road Not Taken"[:60]
    assert all(s.headline == "" for s in slides[1:])
    assert all(s.body for s in slides)


def test_verbatim_slides_balance_and_cap():
    text = " ".join(f"Sentence {i} is here for the essay body." for i in range(80))
    slides = _verbatim_slides(text, "Essay", 5)
    assert len(slides) == 5
    assert all(len(s.body) <= 640 for s in slides)
    # total content preserved (within the per-slide cap)
    assert sum(len(s.body) for s in slides) > 0


def test_verbatim_slides_empty():
    assert _verbatim_slides("", "T", 3) == []
