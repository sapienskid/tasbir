"""Versioned decision question packs (Clef System One schema).

Each pack: ``questions`` (1–12, parallel), ``providers`` (primary → fallback),
``thresholds`` (applied in code, never in the model), ``version`` (bump on any
question/criteria/threshold change; replay the labeled set).

Conventions: question IDs are response keys only (the model never sees them);
``instructions`` carry the full question with backtick refs to state fields.
"""

from __future__ import annotations

PACKS: dict[str, dict] = {
    "intake-router": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"category_min_confidence": 0.5, "safety_block": 0.8},
        "questions": {
            "category": {
                "type": "choice",
                "instructions": "Which approved category label fits `content` best?",
                "criteria": {
                    "PORTFOLIO": "Project showcase posts",
                    "PROJECT": "Individual build/ship updates",
                    "WRITING": "Blog posts and essays",
                    "NOTE": "Short-form thoughts",
                    "other": "None of the above fits",
                },
            },
            "ground": {
                "type": "choice",
                "instructions": "Which canvas ground suits `content`?",
                "criteria": {
                    "white": "Light, open, default editorial ground",
                    "black": "Dark, dramatic, quiet-confidence ground",
                },
            },
            "post_type": {
                "type": "choice",
                "instructions": "What kind of post is `content`?",
                "criteria": {
                    "default": "Standard editorial post",
                    "quote": "Centered on a quotation",
                    "promo": "Promotes something with a call to action",
                    "event": "Announces a dated event",
                    "product": "Showcases a product with price/CTA",
                    "comparison": "Compares options with a key figure",
                    "tutorial": "Teaches steps with a metric",
                    "other": "None of the above",
                },
            },
            "needs_human": {
                "type": "noul",
                "instructions": "Is `content` ambiguous, sensitive, or self-contradictory enough to need a human review?",
            },
            "safety_flag": {
                "type": "noul",
                "instructions": "Does `content` contain hate, harassment, or disallowed material?",
            },
            "complexity": {
                "type": "score",
                "instructions": "How much background does `content` need to be understood?",
                "criteria": ["Standalone", "Some context helps", "Needs research"],
            },
        },
    },
    "planner-gate": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {},
        "questions": {
            "structure": {
                "type": "choice",
                "instructions": "Which post structure fits `content` best?",
                "criteria": {
                    "single": "One frame says it all",
                    "carousel": "A swipeable multi-frame story",
                    "story": "Tall full-screen story format",
                },
            },
            "carousel_worthy": {
                "type": "noul",
                "instructions": "Does `content` have 2+ distinct points that deserve separate frames?",
            },
            "slide_bucket": {
                "type": "choice",
                "instructions": "How many frames does `content` need?",
                "criteria": {
                    "2": "Two frames",
                    "3": "Three frames",
                    "4": "Four frames",
                    "5plus": "Five or more frames",
                },
            },
        },
    },
    "template-pick": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {},
        "questions": {
            "no_fit": {
                "type": "noul",
                "instructions": "Does `content` suit none of the listed templates (needs free-form design)?",
            },
        },
    },
    "media-kind": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"photo_vote": 0.4},
        "questions": {
            "kind": {
                "type": "choice",
                "instructions": "What media should illustrate `content`?",
                "criteria": {
                    "photo": "A real photograph fits the subject",
                    "illustration": "An abstract or avatar illustration fits",
                    "chart": "A stat-led bar chart fits",
                    "none": "Pure typography, no media",
                },
            },
            "photo_worthy": {
                "type": "noul",
                "instructions": "Does `content` describe a concrete, photographable subject?",
            },
        },
    },
    "copy-voice": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"hype_block": 3.0},
        "questions": {
            "tone": {
                "type": "choice",
                "instructions": "What tone does `copy` read in?",
                "criteria": {
                    "professional": "Clean, measured editorial voice",
                    "warm": "Friendly but still professional",
                    "sophisticated": "Quiet, confident, high-end",
                    "hype": "Clickbait, exaggerated, salesy",
                    "off-brand": "Does not fit any brand voice",
                },
            },
            "formality": {
                "type": "score",
                "instructions": "How formal is `copy`?",
                "criteria": ["Casual", "Balanced", "Formal"],
            },
            "hype": {
                "type": "score",
                "instructions": "How hyped or salesy is `copy`?",
                "criteria": ["Restrained", "Confident", "Pushy", "Clickbait"],
            },
            "brand_fit": {
                "type": "noul",
                "instructions": "Does `copy` sound like this brand's editorial voice?",
            },
            "audience": {
                "type": "choice",
                "instructions": "Who is `copy` written for?",
                "criteria": {
                    "beginner": "Newcomers, plain language",
                    "practitioner": "Working practitioners",
                    "expert": "Deep experts",
                    "mixed": "General audience",
                },
            },
        },
    },
    "copy-claims": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"block": 0.8},
        "questions": {
            "absolute_claim": {
                "type": "noul",
                "instructions": "Does `copy` make absolute claims (best ever, guaranteed, always)?",
            },
            "unverifiable_stat": {
                "type": "noul",
                "instructions": "Does `copy` cite a statistic with no source?",
            },
            "price_or_promise": {
                "type": "noul",
                "instructions": "Does `copy` mention prices, guarantees, or promises?",
            },
            "jargon": {
                "type": "score",
                "instructions": "How jargon-heavy is `copy`?",
                "criteria": ["Plain", "Some terms", "Dense jargon"],
            },
            "misleading": {
                "type": "noul",
                "instructions": "Could `copy` mislead a reasonable reader?",
            },
        },
    },
    "copy-structure": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {},
        "questions": {
            "has_hook": {
                "type": "noul",
                "instructions": "Does `copy` open with a clear hook?",
            },
            "has_cta": {
                "type": "choice",
                "instructions": "What call to action does `copy` carry?",
                "criteria": {
                    "explicit": "A direct CTA is present",
                    "implicit": "An implied next step only",
                    "none": "No CTA at all",
                },
            },
            "value_clear": {
                "type": "noul",
                "instructions": "Is the value proposition of `copy` clear within seconds?",
            },
            "density": {
                "type": "choice",
                "instructions": "How dense is `copy`?",
                "criteria": {
                    "punchy": "Tight and scannable",
                    "standard": "Normal editorial density",
                    "dense": "Overloaded, needs trimming",
                },
            },
        },
    },
    "verifier-pregate": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"retry": 0.7},
        "questions": {
            "retry_needed": {
                "type": "noul",
                "instructions": "Given `notes`, does this render likely need a designer retry?",
            },
            "severity": {
                "type": "score",
                "instructions": "How severe are the noted issues in `notes`?",
                "criteria": ["Cosmetic", "Noticeable", "Blocking"],
            },
            "copy_risk": {
                "type": "noul",
                "instructions": "Do `notes` suggest copy overflow, truncation, or clipping risk?",
            },
        },
    },
    "verifier-visual": {
        "version": 1,
        "providers": ["clef", "clef-flash"],
        "thresholds": {
            # A flag becomes "hard" (caps the score, forces retry) only when
            # the judgment is both strong and decisive — an unsure model must
            # not burn designer retries.
            "hard_noul": 0.6,
            "hard_conf": 0.4,
        },
        "questions": {
            "ground_correct": {
                "type": "noul",
                "instructions": "Does the screenshot use the expected ground (light/dark per `notes`)?",
            },
            "has_overflow": {
                "type": "noul",
                "instructions": "Does any text visibly clip, overflow, or collide in the screenshot?",
            },
            "hierarchy_ok": {
                "type": "noul",
                "instructions": "Is the headline clearly dominant with a readable supporting layer?",
            },
            "footer_present": {
                "type": "noul",
                "instructions": "Is a small footer/handle line visible near the bottom edge?",
            },
            "emoji_present": {
                "type": "noul",
                "instructions": "Are colorful emoji or pictographs visible anywhere?",
            },
            "cohesion": {
                "type": "score",
                "instructions": "How visually cohesive is the screenshot?",
                "criteria": ["Scattered", "Mostly unified", "Fully cohesive"],
            },
        },
    },
    "sequence-cohesion": {
        "version": 1,
        "providers": ["clef", "clef-flash"],
        "thresholds": {},
        "questions": {
            "cohesive": {
                "type": "noul",
                "instructions": "Do these carousel frames read as one ordered story?",
            },
            "repetitive": {
                "type": "noul",
                "instructions": "Do two or more frames repeat the same visual or line?",
            },
            "flow": {
                "type": "score",
                "instructions": "How well does the set flow in order?",
                "criteria": ["Broken", "Passable", "Smooth story"],
            },
        },
    },
    "headline-hook": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"weak_hook": 0.4},
        "questions": {
            "has_hook": {
                "type": "noul",
                "instructions": "Does `headline` work as a hook (makes the reader want the next line)?",
            },
            "concrete": {
                "type": "noul",
                "instructions": "Does `headline` name something concrete (a thing, number, or outcome)?",
            },
            "curiosity": {
                "type": "score",
                "instructions": "How much curiosity does `headline` create?",
                "criteria": ["Flat statement", "Mild interest", "Must read on"],
            },
        },
    },
    "design-brief": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {},
        "questions": {
            "has_headline": {
                "type": "noul",
                "instructions": "Does `html` render one dominant headline?",
            },
            "readable_body": {
                "type": "noul",
                "instructions": "Does `html` carry a readable supporting text layer (subhead or body)?",
            },
            "single_focus": {
                "type": "noul",
                "instructions": "Does `html` communicate one idea (not two competing messages)?",
            },
            "craft": {
                "type": "score",
                "instructions": "How finished does `html` feel as a designed post?",
                "criteria": ["Rough draft", "Decent layout", "Publication-ready"],
            },
        },
    },
    "critique-actionable": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"actionable": 0.5},
        "questions": {
            "actionable": {
                "type": "noul",
                "instructions": "Does `critique` name at least one concrete fix (not just a verdict)?",
            },
            "specific": {
                "type": "noul",
                "instructions": "Does `critique` point at a specific element or region (not vague overall)?",
            },
        },
    },
    "publish-gate": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"block": 0.6},
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": "Given `evidence` (scores, issues, copy verdicts), should this post go out?",
                "criteria": {
                    "publish": "Clean enough to share as-is",
                    "hold": "Has a defect the audience would notice — do not share",
                },
            },
            "blocker": {
                "type": "noul",
                "instructions": "Does `evidence` describe a defect the audience would notice?",
            },
        },
    },
    "content-judge": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {},
        "questions": {
            "theme": {
                "type": "choice",
                "instructions": "Which single theme best describes `content`?",
                "criteria": {
                    "technical": "Engineering, systems, code, infrastructure",
                    "product": "Shipping features, user-facing product work",
                    "writing": "Essay, argument, teaching, narrative",
                    "business": "Strategy, market, economics, org",
                    "research": "Findings, studies, experiments, analysis",
                    "other": "None of the above fits",
                },
            },
            "structure": {
                "type": "choice",
                "instructions": "How is `content` best structured for a social post?",
                "criteria": {
                    "single_claim": "One claim the whole piece argues",
                    "steps": "A sequence of steps or stages",
                    "comparison": "A comparison or trade-off",
                    "narrative": "A story with before/after",
                    "reference": "A reference list or cheat sheet",
                    "other": "None of the above fits",
                },
            },
            "has_numbers": {
                "type": "noul",
                "instructions": "Does `content` contain concrete figures, metrics, or dates?",
            },
            "has_quote": {
                "type": "noul",
                "instructions": "Does `content` contain a sentence quotable verbatim?",
            },
            "needs_detail": {
                "type": "score",
                "instructions": "How much context does a reader need before the main point lands?",
                "criteria": ["Lands immediately", "One sentence of setup", "Needs real setup"],
            },
        },
    },
    "refine-focus": {
        "version": 1,
        "providers": ["clef-flash", "clef"],
        "thresholds": {"confidence_gate": 0.5},
        "questions": {
            "focus": {
                "type": "choice",
                "instructions": "Which single fix moves `failed_format` furthest toward passing?",
                "criteria": {
                    "fix_overflow": "Text clips, overflows, or collides with other elements",
                    "restore_missing_element": "A required element (footer handle, category label, accent) is absent",
                    "fix_hierarchy": "The headline does not dominate or the layout reads as flat",
                    "tighten_copy": "Body or subhead is too long, vague, or off-voice",
                    "simplify_ground": "Wrong canvas ground or an off-system colour treatment",
                    "rebalance_layout": "Elements are unbalanced, crowded to one side, or empty",
                    "other": "None of the above fits",
                },
            },
            "worth_retry": {
                "type": "noul",
                "instructions": "Is this fix reachable by editing the HTML/CSS (not by inventing content)?",
            },
            "severity": {
                "type": "score",
                "instructions": "How badly does `failed_format` violate its spec?",
                "criteria": ["Cosmetic drift", "Visible defect", "Spec violation"],
            },
        },
    },
    "image-relevance": {
        "version": 1,
        "providers": ["clef", "clef-flash"],
        "thresholds": {"relevant": 0.5, "clash": 0.6, "min_conf": 0.3},
        "questions": {
            "relevant": {
                "type": "noul",
                "instructions": "Does the attached image illustrate `headline` (not just decorate)?",
            },
            "text_clash": {
                "type": "noul",
                "instructions": "Does the attached image fight the overlaid text (busy behind words)?",
            },
        },
    },
}


# Post-type extras spec: which optional fields each post type must fill, and
# what each one means. Used to build per-post extras-check questions.
POST_TYPE_EXTRAS: dict[str, dict[str, str]] = {
    "quote": {"source": "the author/source of the quote"},
    "promo": {"cta": "a short call to action"},
    "event": {"date": "date/time", "location": "venue or link"},
    "product": {"price": "price", "cta": "call to action"},
    "comparison": {"stat": "the key figure being compared"},
    "tutorial": {"stat": "count or metric (e.g. '5 steps')"},
}


def refine_brief(answers: dict, attempt: int, max_retries: int) -> str:
    """Turn ``refine-focus`` answers into a targeted retry instruction.

    The retry loop is the decision model's payoff: one cheap flash call
    picks the single highest-leverage fix and this renders it as a short,
    imperative brief the next design attempt can follow. Returns "" when the
    model judged the format not worth retrying (the loop stops early).
    """
    if not answers:
        return ""
    try:
        worth = float((answers.get("worth_retry") or {}).get("noul", 0.0) or 0.0)
    except (TypeError, ValueError):
        worth = 0.0
    try:
        confidence = float((answers.get("focus") or {}).get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    choice = str((answers.get("focus") or {}).get("choice") or "")
    if not choice or choice == "other":
        return ""
    # Not confident what to fix, or not reachable from HTML/CSS: don't spin.
    if confidence < 0.5 or worth < 0.5:
        return ""
    attempts_left = max(0, max_retries - attempt + 1)
    return (
        f"RETRY FOCUS (attempt {attempt + 1}, {attempts_left} left) — the "
        f"decision model picked `{choice}` as the single highest-leverage fix. "
        f"Make that fix and change nothing else."
    )


def extras_questions(post_type: str, extra_keys: list[str]) -> dict:
    """Build extras-check questions for a post type.

    One presence Noul per expected extra + one groundedness Noul (every
    filled extra must be supported by the source). Empty when the post type
    (or its extras) calls for nothing — the caller skips the decision call.
    """
    spec = POST_TYPE_EXTRAS.get(post_type or "default", {})
    questions: dict = {}
    for key in extra_keys:
        if key not in spec:
            continue
        questions[f"{key}_present"] = {
            "type": "noul",
            "instructions": f"Does `copy` state the {spec[key]} ({key}) clearly?",
        }
    if questions:
        questions["grounded"] = {
            "type": "noul",
            "instructions": "Is every extra in `copy` supported by `source` (nothing invented)?",
        }
    return questions


def get_pack(pack_id: str) -> dict:
    try:
        return PACKS[pack_id]
    except KeyError:
        raise ValueError(f"Unknown decision pack: {pack_id}")


def list_packs() -> list[dict]:
    return [
        {
            "id": pid,
            "version": pack.get("version", 1),
            "providers": list(pack.get("providers") or []),
            "questions": sorted(pack.get("questions", {}).keys()),
        }
        for pid, pack in sorted(PACKS.items())
    ]


def copy_quality(voice: dict, claims: dict, structure: dict) -> dict:
    """Composite marketing-copy score in code (never one mega-question).

    Weights: brand 0.35, clarity 0.25, CTA 0.2, platform-readiness 0.2.
    Each dimension is derived from its pack's answers; thresholds gate
    auto-pass (≥0.80), human-first (0.60–0.80), rewrite (<0.60).
    """
    from app.services.decisions import noul_confidence

    def _noul(ans: dict | None) -> float:
        if not ans:
            return 0.5
        try:
            return float(ans.get("noul", 0.5))
        except (TypeError, ValueError):
            return 0.5

    brand = _noul((voice.get("brand_fit")) if isinstance(voice, dict) else None)
    hype = voice.get("hype", {}) if isinstance(voice, dict) else {}
    try:
        hype_score = float(hype.get("score", 1.5))
    except (TypeError, ValueError):
        hype_score = 1.5
    brand_dim = max(0.0, min(1.0, brand * (1.0 - max(0.0, hype_score - 1.0) / 6.0)))
    clarity = 1.0 - _noul(claims.get("misleading")) if isinstance(claims, dict) else 0.5
    cta_ans = (structure.get("has_cta") or {}) if isinstance(structure, dict) else {}
    cta_dim = {"explicit": 1.0, "implicit": 0.6, "none": 0.2}.get(cta_ans.get("choice"), 0.5)
    value_dim = _noul(structure.get("value_clear")) if isinstance(structure, dict) else 0.5
    score = round(0.35 * brand_dim + 0.25 * clarity + 0.2 * cta_dim + 0.2 * value_dim, 3)
    verdict = "pass" if score >= 0.80 else ("review" if score >= 0.60 else "rewrite")
    _ = noul_confidence  # confidence helper stays coupled to this module's tests
    return {
        "score": score,
        "verdict": verdict,
        "dims": {"brand": round(brand_dim, 3), "clarity": round(clarity, 3),
                 "cta": round(cta_dim, 3), "value": round(value_dim, 3)},
    }
