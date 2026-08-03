"""Tests for the verbatim carousel copy mode."""

import sys

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


def test_verbatim_slides_balanced_essay():
    """Long essay prose fills every slide substantially — no near-empty middles."""
    paras = [
        "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.",
        "Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure. We are met on a great battlefield of that war.",
        "We have come to dedicate a portion of that field, as a final resting place for those who here gave their lives that that nation might live. It is altogether fitting and proper that we should do this.",
        "But, in a larger sense, we can not dedicate — we can not consecrate — we can not hallow — this ground. The brave men, living and dead, who struggled here, have consecrated it, far above our poor power to add or detract.",
        "The world will little note, nor long remember what we say here, but it can never forget what they did here. It is for us the living, rather, to be dedicated here to the unfinished work which they who fought here have thus far so nobly advanced.",
        "It is rather for us to be here dedicated to the great task remaining before us — that from these honored dead we take increased devotion to that cause for which they gave the last full measure of devotion.",
        "That we here highly resolve that these dead shall not have died in vain — that this nation, under God, shall have a new birth of freedom — and that government of the people, by the people, for the people, shall not perish from the earth.",
    ]
    text = "\n\n".join(paras)
    n = 5
    slides = _verbatim_slides(text, "The Gettysburg Address", n)
    assert len(slides) == 5
    assert all(s.body for s in slides)  # no empty slide
    target = len(text) / n
    # no slide is near-empty: every slide carries at least a quarter of target
    assert all(len(s.body) >= target * 0.25 for s in slides)
    # order preserved: the essay's first and last phrases stay on first/last slides
    assert slides[0].body.startswith("Four score and seven years ago")
    assert "shall not perish from the earth" in slides[-1].body
    # cover title only
    assert slides[0].headline == "The Gettysburg Address"[:60]
    assert all(s.headline == "" for s in slides[1:])
