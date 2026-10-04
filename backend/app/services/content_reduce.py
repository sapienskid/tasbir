"""Long-content handling — Gemini reads, Clef judges, Gemma writes.

The Google free tier's scarcest resource is **tokens per minute**, and Gemma
has only 16K TPM. A 5,000-word article is ~6.7K input tokens before any
system prompt, so two or three calls per run would exhaust a model's whole
minute and start returning 429s mid-pipeline.

Each model is used for what it is actually good at:

* **Gemini 3.1 Flash Lite — reads.** 250K TPM means it can ingest a long
  article in a single call and emit a compressed editorial brief. This is a
  *generative* pass (it writes text), which is exactly why it is Gemini and
  not a decision model.
* **Clef-flash — judges.** No text generation at all: it returns calibrated
  probabilities for the questions we pose. Used to classify the article
  (theme, structure, has-facts, has-quote) and to pick the framing, so the
  Gemini compression prompt is aimed instead of generic.
* **Gemma — writes.** 16K TPM but 14.4K requests/day, so it should only ever
  see the compressed brief plus a short excerpt, never the raw article.

The net effect: one large call against the generous tier instead of N large
calls against the scarce one.
"""

from __future__ import annotations

import json
import logging
import re

log = logging.getLogger(__name__)

# Above this we reduce instead of passing raw content. ~12K chars ≈ 3K tokens,
# which still fits Gemma's 16K TPM once a system prompt is added.
REDUCE_THRESHOLD_CHARS = 12_000
# Hard ceiling on what a Google model ever receives, whatever reduction did.
MAX_GOOGLE_CONTENT_CHARS = 6_000
# Raw excerpt kept alongside the brief so agents can quote verbatim.
EXCERPT_CHARS = 1_500
# The reading model — the tier with 250K TPM.
READER_MODEL = "gemini-3.1-flash-lite"


def needs_reduction(content: str) -> bool:
    return len(content or "") > REDUCE_THRESHOLD_CHARS


def _excerpt(content: str, n: int = EXCERPT_CHARS) -> str:
    return " ".join((content or "").split())[:n]


# ---------------------------------------------------------------------------
# Stage 1 — Clef judges (no text generation, Neuron-billed)
# ---------------------------------------------------------------------------

JUDGE_QUESTIONS: dict = {
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
}


async def judge_content(content: str, title: str = "") -> dict:
    """Clef classification pass. Returns ``{}`` when unavailable."""
    try:
        from app.services.decisions import decide, providers_configured

        if not providers_configured():
            return {}
        res = await decide(
            "content-judge",
            {"content": content, "title": title},
            questions=dict(JUDGE_QUESTIONS),
            metadata={"agent": "strategist", "pack": "content-judge"},
        )
        answers = res.get("answers", {})
        return {
            "theme": str((answers.get("theme") or {}).get("choice") or ""),
            "structure": str((answers.get("structure") or {}).get("choice") or ""),
            "has_numbers": _noul(answers, "has_numbers"),
            "has_quote": _noul(answers, "has_quote"),
            "needs_detail": (answers.get("needs_detail") or {}).get("score"),
            "provider": res.get("provider", ""),
        }
    except Exception as e:  # noqa: BLE001
        log.warning("[reduce] clef judge pass failed: %s", e)
        return {}


def _noul(answers: dict, qid: str) -> float:
    try:
        return float((answers.get(qid) or {}).get("noul", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Stage 2 — Gemini compresses (generative, high-TPM tier)
# ---------------------------------------------------------------------------

_COMPRESS_SYSTEM = (
    "You compress a long article into an editorial brief for a social-media "
    "writer. You never invent facts and never add commentary.\n\n"
    "Return ONLY a JSON object with these keys:\n"
    '  "thesis": one sentence stating the article\'s single main claim\n'
    '  "points": 3-6 short strings, each a distinct point with any figure '
    "preserved verbatim\n"
    '  "quote": one quotable sentence copied verbatim from the article, or ""\n'
    '  "hook_fact": the most concrete number/fact/change stated, or ""\n'
    '  "entities": 0-5 proper nouns central to the article\n'
    '  "angle": one sentence on how to frame this as a post\n'
)


def _compress_user_prompt(content: str, title: str, verdict: dict) -> str:
    hints = []
    if verdict.get("theme"):
        hints.append(f"A classification pass judged the theme as: {verdict['theme']}.")
    if verdict.get("structure"):
        hints.append(f"It judged the best post structure as: {verdict['structure']}.")
    if verdict.get("has_numbers", 0) >= 0.5:
        hints.append("It found concrete figures — preserve them exactly.")
    if verdict.get("has_quote", 0) >= 0.5:
        hints.append("It found a quotable line — copy it verbatim.")
    hint_block = ("\n".join(hints) + "\n\n") if hints else ""
    return (
        f"TITLE: {title or '(untitled)'}\n\n"
        f"{hint_block}"
        f"ARTICLE:\n{content}\n\n"
        "Return ONLY the JSON object."
    )


def _extract_json(text: str) -> dict | None:
    t = (text or "").strip()
    try:
        data = json.loads(t)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"```\s*$", "", t, flags=re.MULTILINE)
    try:
        data = json.loads(t.strip())
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


async def compress_with_llm(
    content: str, title: str, verdict: dict, model: str = READER_MODEL
) -> dict:
    """One high-TPM call that turns the article into a brief.

    Returns the parsed brief dict, or {} on any failure (the caller then
    falls back to the excerpt path).
    """
    try:
        from app.services.llm import call_llm

        raw = await call_llm(
            agent_role="strategist",
            system_prompt=_COMPRESS_SYSTEM,
            user_prompt=_compress_user_prompt(content, title, verdict),
            temperature=0.3,
            max_tokens=1200,
        )
        data = _extract_json(raw)
        if not data:
            log.warning("[reduce] compression output unparseable — using excerpt")
            return {}
        points = data.get("points")
        if isinstance(points, str):
            points = [points]
        if not isinstance(points, list):
            points = []
        return {
            "thesis": str(data.get("thesis") or "")[:400],
            "points": [str(p)[:300] for p in points][:6],
            "quote": str(data.get("quote") or "")[:400],
            "hook_fact": str(data.get("hook_fact") or "")[:200],
            "entities": [str(e)[:60] for e in (data.get("entities") or [])][:5]
            if isinstance(data.get("entities"), list) else [],
            "angle": str(data.get("angle") or "")[:300],
        }
    except Exception as e:  # noqa: BLE001
        log.warning("[reduce] compression call failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Stage 3 — assemble what the downstream agents will read
# ---------------------------------------------------------------------------


def compose_brief(
    content: str, title: str, brief: dict, verdict: dict
) -> str:
    """Build the compact context block for strategist / copywriter."""
    excerpt = _excerpt(content)
    lines = [f"SOURCE TITLE: {title or '(untitled)'}"]
    if brief.get("thesis"):
        lines.append(f"THESIS: {brief['thesis']}")
    if brief.get("angle"):
        lines.append(f"SUGGESTED ANGLE: {brief['angle']}")
    for i, point in enumerate(brief.get("points") or [], start=1):
        lines.append(f"POINT {i}: {point}")
    if brief.get("hook_fact"):
        lines.append(f"KEY FACT: {brief['hook_fact']}")
    if brief.get("quote"):
        lines.append(f"QUOTABLE: {brief['quote']}")
    if brief.get("entities"):
        lines.append(f"ENTITIES: {', '.join(brief['entities'])}")
    if verdict.get("theme"):
        lines.append(f"CLASSIFIED THEME: {verdict['theme']}")
    if verdict.get("structure"):
        lines.append(f"CLASSIFIED STRUCTURE: {verdict['structure']}")
    lines.append(
        f"\nORIGINAL OPENING (for grounding and verbatim quotes, "
        f"{len(excerpt)} chars):\n{excerpt}"
    )
    return "\n".join(lines)


async def reduce_content(content: str, title: str = "") -> dict:
    """Full reduction: Clef judges → Gemini compresses → compact brief.

    Returns ``{}`` when the content is short enough to pass through, or when
    both stages fail — callers then use the excerpt path.
    """
    if not needs_reduction(content):
        return {}
    verdict = await judge_content(content, title)
    brief = await compress_with_llm(content, title, verdict)
    if not brief:
        return {}
    log.info(
        "[reduce] %d chars → %d char brief (%d points) via judge=%s reader=%s",
        len(content), len(compose_brief(content, title, brief, verdict)),
        len(brief.get("points") or []), verdict.get("provider", ""), READER_MODEL,
    )
    return {
        "brief": brief,
        "verdict": verdict,
        "reader_model": READER_MODEL,
        "context": compose_brief(content, title, brief, verdict),
        "original_chars": len(content),
    }
