"""Template library — Jinja2-rendered, human-authored post compositions.

Templates live in ``data/design_system/templates/`` as Jinja2 HTML with
``data-slot`` attributes on every content element. The pipeline consults the
library first; only when nothing matches (or the chosen template overflows)
does the LLM designer run.

Two directions are supported:
  - render:  select a template, fill it with copy via Jinja2
  - promote: take rendered/edited HTML, read ``data-slot`` text, and produce a
             fresh template file (the learning loop)
"""

from __future__ import annotations

import hashlib
import html as html_lib
import logging
import re
from html.parser import HTMLParser
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.config import get_settings

log = logging.getLogger(__name__)

_TEMPLATE_ENV: Environment | None = None


def templates_dir() -> Path:
    settings = get_settings()
    return Path(settings.design_system_dir) / "templates"


def catalog_path() -> Path:
    return templates_dir() / "catalog.yaml"


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def load_template_catalog() -> dict:
    """Load templates/catalog.yaml → {"templates": {id: entry}}."""
    path = catalog_path()
    if not path.exists():
        return {"templates": {}}
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict) and isinstance(raw.get("templates"), dict):
            return raw
    except Exception as e:
        log.warning("[templates] Failed to load catalog: %s", e)
    return {"templates": {}}


def save_template_catalog(catalog: dict) -> None:
    """Persist the catalog (used by the promote endpoint)."""
    templates_dir().mkdir(parents=True, exist_ok=True)
    with open(catalog_path(), "w", encoding="utf-8") as f:
        yaml.safe_dump(catalog, f, sort_keys=False, allow_unicode=True)


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


def render_template_file(rel_path: str, context: dict) -> str:
    """Render a Jinja2 template file by its catalog ``file`` path."""
    env = get_environment()
    try:
        tmpl = env.get_template(rel_path)
    except TemplateNotFound:
        log.warning("[templates] Missing template file: %s", rel_path)
        raise
    return tmpl.render(**context)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def format_family(format_id: str) -> str:
    """Map a platform id to its format family (square/portrait/story/landscape)."""
    from app.services.design_instruction import load_design_instruction
    from app.services.tokens import load_platforms

    settings = get_settings()
    di = load_design_instruction(Path(settings.design_system_dir) / "design-instruction.yaml")
    families = di.get("format_families", {})
    if format_id in families:
        return families[format_id]
    platforms = load_platforms(settings.platforms_path)
    if format_id in platforms:
        return "square" if platforms[format_id][1] <= platforms[format_id][0] else "portrait"
    return "square"


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
    exclude: set[str] | None = None,
) -> tuple[str, dict] | None:
    """Pick a template deterministically for the given post context.

    Filters by family + ground, ranks by category affinity + strategist hint
    + a seeded jitter, and excludes recently-used ids (anti-repetition).
    """
    exclude = exclude or set()
    catalog = load_template_catalog().get("templates", {})
    candidates = {
        tid: e
        for tid, e in catalog.items()
        if e.get("family") == family and ground in e.get("grounds", ["white", "black"])
    }
    if not candidates:
        return None

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
) -> dict:
    """Build the Jinja2 render context from typed copy + design decisions."""
    # Deterministic index numeral (editorial device, varies per post).
    digest = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6], 16) if seed else 1
    loop_index = (digest % 27) + 1
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
        "meta": meta,
        "loop_index": loop_index,
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
            # void element with data-slot — treat as empty
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
    return joined


def save_template(rel_file: str, html: str) -> Path:
    """Write a template file into the library directory."""
    path = templates_dir() / rel_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    log.info("[templates] Saved template %s", path)
    return path


# ---------------------------------------------------------------------------
# Anti-repetition (recently used template ids, Redis)
# ---------------------------------------------------------------------------

_RECENT_KEY = "tpl:recent"
_RECENT_LIMIT = 8


async def get_recent_template_ids(limit: int = _RECENT_LIMIT) -> set[str]:
    """Return template ids used on the most recent posts (anti-repetition)."""
    from redis.asyncio import Redis

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
        await redis.lpush(_RECENT_KEY, template_id)
        await redis.ltrim(_RECENT_KEY, 0, _RECENT_LIMIT - 1)
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
    "save_template",
    "save_template_catalog",
    "select_template",
    "slotize_html",
    "templates_dir",
]
