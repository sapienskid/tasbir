"""Template library — Jinja2-rendered, DB-backed post compositions.

Templates live in the ``templates`` table (v0.5), scoped to a design system.
The pipeline consults the library first; only when nothing matches (or the
chosen template overflows) does the LLM designer run.

Two directions are supported:
  - render:  select a template, fill it with copy via Jinja2
  - promote: take rendered/edited HTML, read ``data-slot`` text, and produce a
             fresh template row (the learning loop)

The file-based catalog helpers (``load_template_catalog`` etc.) remain only
for the first-boot seed that imports the legacy YAML templates into the DB.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import logging
import re
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.config import get_settings
from app.services.illustration import generate_illustration_svg

log = logging.getLogger(__name__)

_TEMPLATE_ENV: Environment | None = None


def templates_dir() -> Path:
    settings = get_settings()
    return Path(settings.design_system_dir) / "templates"


def catalog_path() -> Path:
    return templates_dir() / "catalog.yaml"


# ---------------------------------------------------------------------------
# Legacy file catalog (seeding only)
# ---------------------------------------------------------------------------


def load_template_catalog() -> dict:
    """Load templates/catalog.yaml → {"templates": {id: entry}} (seed path)."""
    path = catalog_path()
    if not path.exists():
        return {"templates": {}}
    try:
        with open(path, encoding="utf-8") as f:
            raw = __import__("yaml").safe_load(f)
        if isinstance(raw, dict) and isinstance(raw.get("templates"), dict):
            return raw
    except Exception as e:
        log.warning("[templates] Failed to load catalog: %s", e)
    return {"templates": {}}


# ---------------------------------------------------------------------------
# Jinja2 environment
# ---------------------------------------------------------------------------


def get_environment() -> Environment:
    global _TEMPLATE_ENV
    if _TEMPLATE_ENV is None:
        _TEMPLATE_ENV = Environment(
            loader=FileSystemLoader(str(templates_dir())),
            autoescape=True,
            cache_size=200,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _TEMPLATE_ENV


def render_template_html(html: str, context: dict) -> str:
    """Render a Jinja2 template string with the given context."""
    env = get_environment()
    return env.from_string(html).render(**context)


def render_template_file(rel_path: str, context: dict) -> str:
    """Render a Jinja2 template file (legacy/seed path)."""
    env = get_environment()
    try:
        tmpl = env.get_template(rel_path)
    except TemplateNotFound:
        log.warning("[templates] Missing template file: %s", rel_path)
        raise
    return tmpl.render(**context)


# ---------------------------------------------------------------------------
# DB row → selection entry
# ---------------------------------------------------------------------------


def template_to_dict(row) -> dict:
    """Convert a Template ORM row to the dict shape selection expects."""
    return {
        "id": row.id,
        "name": row.name,
        "family": row.family,
        "grounds": row.grounds or ["white", "black"],
        "categories": row.categories or [],
        "hint_tags": row.hint_tags or [],
        "weight": float(row.weight or 1.0),
        "description": row.description or "",
        "html": row.html,
        "image_slots": row.image_slots or [],
        "has_logo_slot": bool(row.has_logo_slot),
        "design_system_id": row.design_system_id,
        "source": row.source,
        "is_active": bool(row.is_active),
    }


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def format_family(format_id: str) -> str:
    """Map a platform id to its format family (square/portrait/story/landscape).

    Resolved from the DB platforms table (family stored at seed from the
    design-instruction format_families map, aspect heuristic fallback).
    """
    from app.services.platforms import family_of

    fam = family_of(format_id)
    return fam if fam in ("square", "portrait", "story", "landscape") else "square"


def _hint_overlap(hint: str, entry: dict, tid: str) -> bool:
    if not hint:
        return False
    h = hint.lower().strip()
    if h == tid or tid.endswith("-" + h) or tid == h:
        return True
    tags = [str(t).lower() for t in entry.get("hint_tags", [])]
    if h in tags:
        return True
    h_tokens = {t for t in h.replace("-", " ").split() if len(t) > 2}
    for t in tags:
        t_tokens = {x for x in t.replace("-", " ").split() if len(x) > 2}
        if h_tokens and h_tokens & t_tokens:
            return True
    return False


def select_template(
    family: str,
    ground: str,
    category: str,
    hint: str,
    seed: str,
    templates: list[dict],
    exclude: set[str] | None = None,
    prefer: str | None = None,
) -> tuple[str, dict] | None:
    """Pick a template deterministically from a loaded template list.

    Filters by family + ground, ranks by category affinity + strategist hint
    + a seeded jitter, and excludes recently-used ids (anti-repetition).
    ``templates`` is the list of template dicts (see ``template_to_dict``) —
    a pure function, so it stays testable without a DB session. ``prefer``
    biases toward templates carrying that ``hint_tag`` (e.g. ``"media"`` /
    ``"text"`` for carousel layout variety); falls back if none match.
    """
    exclude = exclude or set()
    candidates = {
        t["id"]: t
        for t in templates
        if t.get("family") == family
        and ground in t.get("grounds", ["white", "black"])
    }
    if not candidates:
        return None

    if prefer:
        preferred = {
            tid: e
            for tid, e in candidates.items()
            if prefer in {str(h).lower() for h in e.get("hint_tags", [])}
        }
        if preferred:
            candidates = preferred

    # The strategist's hint is the strongest signal — if it names an
    # available template for this family+ground, honor it directly.
    if hint:
        h = hint.lower().strip()
        if h in candidates:
            return h, candidates[h]
        for tid in candidates:
            if tid.endswith("-" + h):
                return tid, candidates[tid]

    pool = {tid: e for tid, e in candidates.items() if tid not in exclude}
    if not pool:
        pool = candidates

    best_tid, best_score = None, -1e9
    for tid, entry in pool.items():
        score = float(entry.get("weight", 1.0)) * 0.1
        if category and category in {str(c).upper() for c in entry.get("categories", [])}:
            score += 4.0
        if _hint_overlap(hint, entry, tid):
            score += 3.0
        # Seeded jitter so the same content always lands on the same template,
        # different content varies — reproducibility with variety.
        digest = int(hashlib.sha1(f"{seed}|{tid}".encode("utf-8")).hexdigest()[:8], 16)
        score += (digest % 1000) / 1000.0
        if score > best_score:
            best_tid, best_score = tid, score

    if best_tid is None:
        return None
    return best_tid, pool[best_tid]


# ---------------------------------------------------------------------------
# Filling
# ---------------------------------------------------------------------------


def build_template_context(
    copy: dict,
    category: str,
    ground: str,
    footer: dict,
    width: int,
    height: int,
    has_image: bool,
    meta: str = "",
    seed: str = "",
    family: str = "square",
    logo: str = "",
    di_config: dict | None = None,
    illustration: str | None = None,
    slide_index: int = 0,
    slide_total: int = 0,
) -> dict:
    """Build the Jinja2 render context from typed copy + design decisions."""
    # Deterministic index numeral (editorial device, varies per post).
    digest = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6], 16) if seed else 1
    loop_index = (digest % 27) + 1

    # Deterministic decorative glyph texture — typographic, monochrome-safe, and
    # reproducible per post (seeded), but varies across posts. Avoids hardcoding
    # motifs into templates while staying within the no-illustration rule.
    glyphs = ["+", "−", "×", "÷", "·", "•"]
    digest2 = (hashlib.sha1(f"{seed}|decor".encode("utf-8")).hexdigest() * 2)[:48]
    decor_pattern = [
        glyphs[int(digest2[i : i + 2], 16) % len(glyphs)]
        for i in range(0, 48, 2)
    ]

    # Family-aware type scale: tall formats get larger type to fill the canvas.
    # The DI comes from the caller (task's design system) — no YAML read here.
    base = 1080
    fam_scale = (
        (di_config or {}).get("type_scale", {}).get("family_scale") or {}
    ).get(family, 1.0)
    tscale = float(fam_scale) * (width / base)
    tscale = max(0.6, min(tscale, 2.0))

    # Procedural Anthropic-style illustration. Seeded from the post title alone
    # (not per-format) so every format of a post shares one piece of art. Only
    # templates that reference {{ illustration }} render it. A caller-provided
    # ``illustration`` (e.g. an LLM tool result) wins over the deterministic one.
    if illustration is None:
        ill_seed = f"{seed.split('|')[0]}|illustration" if seed else "illustration"
        illustration = generate_illustration_svg(ill_seed, ground)

    return {
        "kicker": category,
        "headline": copy.get("headline", ""),
        "subhead": copy.get("subhead", ""),
        "body": copy.get("body", ""),
        "tagline": copy.get("tagline", ""),
        "footer_left": (footer or {}).get("left", ""),
        "footer_right": (footer or {}).get("right", ""),
        "ground": ground if ground in ("white", "black") else "white",
        "width": width,
        "height": height,
        "has_image": bool(has_image),
        "has_logo": bool(logo),
        "logo": logo,
        "meta": meta,
        "loop_index": loop_index,
        "decor_pattern": decor_pattern,
        "illustration": illustration,
        "slide_index": slide_index,
        "slide_total": slide_total,
        "tscale": tscale,
    }


# ---------------------------------------------------------------------------
# Promotion (edited HTML → template)
# ---------------------------------------------------------------------------

_INJECTED_STYLE_RE = re.compile(r"<style>\s*:root\s*\{[^}]*\}\s*</style>", re.IGNORECASE)
_CDN_RE = re.compile(
    r'<link[^>]*(?:fonts\.googleapis|fonts\.gstatic)[^>]*>'
    r'|<link[^>]*cdn\.jsdelivr\.net/npm/katex[^>]*>'
    r'|<script[^>]*cdn\.jsdelivr\.net/npm/katex[^>]*>.*?</script>'
    r'|<link[^>]*rel="preconnect"[^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_GROUND_ATTR_RE = re.compile(r'(<body[^>]*)data-ground="black"([^>]*>)', re.IGNORECASE)
_BODY_DIM_RE = re.compile(
    r"(body\s*\{[^}]*?width:\s*)\d+(px;[^}]*?height:\s*)\d+(px)",
    re.IGNORECASE | re.DOTALL,
)
_LOGO_DATA_SRC_RE = re.compile(
    r'(<img[^>]*data-logo[^>]*)src="data:[^"]*"([^>]*>)',
    re.IGNORECASE,
)


def extract_slots(html: str) -> dict[str, str]:
    """Read the current text of every [data-slot] element (for promotion)."""
    class _Extractor(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.slots: dict[str, list[str]] = {}
            self.stack: list[tuple[str, str]] = []

        def handle_starttag(self, tag, attrs):
            slot = None
            for k, v in attrs:
                if k.lower() == "data-slot" and v:
                    slot = v
            self.stack.append((slot, []))
            if slot:
                self.slots.setdefault(slot, [])

        def handle_startendtag(self, tag, attrs):
            slot = None
            for k, v in attrs:
                if k.lower() == "data-slot" and v:
                    slot = v
            if slot:
                self.slots.setdefault(slot, [])

        def handle_data(self, data):
            if self.stack and self.stack[-1][0]:
                self.stack[-1][1].append(data)

        def handle_endtag(self, tag):
            if self.stack:
                slot, parts = self.stack.pop()
                if slot:
                    self.slots[slot].append("".join(parts))

    parser = _Extractor()
    parser.feed(html)
    parser.close()
    return {name: "".join(parts).strip() for name, parts in parser.slots.items()}


def _strip_injected(html: str) -> str:
    """Remove token/font/KaTeX blocks the renderer injects (re-added at render)."""
    html = _INJECTED_STYLE_RE.sub("", html)
    html = _CDN_RE.sub("", html)
    return html


class _Slotizer(HTMLParser):
    """Re-emits HTML, replacing each [data-slot] element's inner text with {{ name }}."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.slot_stack: list[tuple[str, str]] = []  # (tag, slot_name) while buffering

    def _current_slot(self):
        return self.slot_stack[-1] if self.slot_stack else None

    def handle_starttag(self, tag, attrs):
        slot = None
        for k, v in attrs:
            if k.lower() == "data-slot" and v:
                slot = v
        self.out.append(self._open_tag(tag, attrs))
        if slot:
            self.slot_stack.append((tag, slot))

    def handle_startendtag(self, tag, attrs):
        self.out.append(self._open_tag(tag, attrs) + "/>")

    def handle_endtag(self, tag):
        if self.slot_stack and self.slot_stack[-1][0].lower() == tag.lower():
            _, slot = self.slot_stack.pop()
            self.out.append("{{ %s }}" % slot)
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        # Slot content is discarded — the {{ slot }} token replaces it.
        if not self.slot_stack:
            self.out.append(data)

    def handle_decl(self, decl):
        # Preserve <!DOCTYPE html> (base HTMLParser hook is a no-op).
        self.out.append(f"<!{decl}>")

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def _open_tag(self, tag, attrs):
        rendered = [f"<{tag}"]
        for k, v in attrs:
            if v is None:
                rendered.append(k)
            else:
                rendered.append(f'{k}="{html_lib.escape(v, quote=True)}"')
        return " ".join(rendered) + ">"


def slotize_html(html: str) -> str:
    """Turn rendered/edited HTML into a Jinja2 template.

    - strips injected token/font/KaTeX blocks
    - replaces every [data-slot] element's content with {{ slot_name }}
    - restores the black-ground conditional on <body>
    - converts baked base64 <img> back to data-image-key markers
    - rewrites a baked logo data-URI back to src="{{ logo }}"
    """
    html = _strip_injected(html)
    parser = _Slotizer()
    parser.feed(html)
    parser.close()
    out = parser.out

    # Restore ground conditional for the <body> tag.
    joined = "".join(out)
    joined = _GROUND_ATTR_RE.sub(
        r'\1{% if ground == "black" %}data-ground="black"{% endif %}\2', joined
    )

    # Re-parameterize the body canvas size so the promoted template works for
    # every platform in the family (not just the source platform's pixels).
    joined = _BODY_DIM_RE.sub(r"\1{{ width }}\2{{ height }}\3", joined)

    # <img src="data:..."> → <img data-image-key="N"> so images stay content, not layout.
    joined = re.sub(
        r'<img\s+([^>]*?)src="data:[^"]*"([^>]*?)/?>',
        lambda m: f'<img {m.group(1)} data-image-key="0" {m.group(2)}/>',
        joined,
    )

    # Logo stays content too: baked data-URI → src="{{ logo }}".
    joined = _LOGO_DATA_SRC_RE.sub(r'\1src="{{ logo }}"\2', joined)

    return joined


def save_template(rel_file: str, html: str) -> Path:
    """Write a template file into the library directory (legacy path)."""
    path = templates_dir() / rel_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    log.info("[templates] Saved template file %s", path)
    return path


def scan_template_features(html: str) -> tuple[list[dict], bool]:
    """Derive image_slots + has_logo_slot from a template's markers."""
    keys = set(re.findall(r'data-image-key=["\'](\d+)["\']', html))
    image_slots = [
        {"key": k, "role": "image", "hint": f"Image slot {k}"} for k in sorted(keys)
    ]
    has_logo = bool(re.search(r'data-logo["\s]', html)) or "{{ logo }}" in html
    return image_slots, has_logo


# ---------------------------------------------------------------------------
# Anti-repetition (recently used template ids, Redis)
# ---------------------------------------------------------------------------

_RECENT_KEY = "tpl:recent"
_RECENT_LIMIT = 8


async def _recent_limit() -> int:
    from app.services.settings import get_runtime_setting

    return int(await get_runtime_setting("templates.recent_limit", _RECENT_LIMIT))


async def get_recent_template_ids(limit: int | None = None) -> set[str]:
    """Return template ids used on the most recent posts (anti-repetition)."""
    from redis.asyncio import Redis

    if limit is None:
        limit = await _recent_limit()
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        return set(await redis.lrange(_RECENT_KEY, 0, limit))
    except Exception as e:
        log.debug("[templates] Recent-list read failed: %s", e)
        return set()
    finally:
        await redis.aclose()


async def push_recent_template_id(template_id: str) -> None:
    """Record that a template was just used, trimming the list."""
    from redis.asyncio import Redis

    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        limit = await _recent_limit()
        await redis.lpush(_RECENT_KEY, template_id)
        await redis.ltrim(_RECENT_KEY, 0, limit - 1)
        await redis.expire(_RECENT_KEY, 7 * 24 * 3600)
    except Exception as e:
        log.debug("[templates] Recent-list write failed: %s", e)
    finally:
        await redis.aclose()


__all__ = [
    "build_template_context",
    "catalog_path",
    "extract_slots",
    "format_family",
    "get_environment",
    "get_recent_template_ids",
    "load_template_catalog",
    "push_recent_template_id",
    "render_template_file",
    "render_template_html",
    "save_template",
    "scan_template_features",
    "select_template",
    "slotize_html",
    "template_to_dict",
    "templates_dir",
]
