"""``find_photo`` — search stock photos across providers (LLM tool).

One vetted candidate per call, in provider fallback order
(Pexels → Pixabay → Wikimedia). Providers without a configured key are
skipped. Candidates are filtered by minimum dimension and orientation before
the best one is returned, so the LLM can re-call with a refined query instead
of parsing a shortlist.

The handler returns a candidate dict; embedding (download → base64 → inject
into template HTML) happens in the pipeline via :func:`embed_photo_into_html`.
"""

from __future__ import annotations

import base64
import html as html_lib
import logging
import re

import httpx

from app.config import get_settings
from app.services.ssrf import check_image_url
from app.services.tools.providers.pexels import search_pexels
from app.services.tools.providers.pixabay import search_pixabay
from app.services.tools.providers.wikimedia import search_wikimedia

log = logging.getLogger(__name__)

FIND_PHOTO_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "find_photo",
        "description": (
            "Search royalty-free stock photos for the post and return the best "
            "single candidate. Call once with a concrete query; if the returned "
            "image doesn't fit the post, call again with a refined query. The "
            "photo is automatically converted to grayscale and credited on the "
            "post."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A concrete search query matching the post's subject, "
                        "e.g. 'minimal typography on paper', 'city skyline fog'. "
                        "Prefer terms that lead to clean, compositionally calm "
                        "photos."
                    ),
                },
                "orientation": {
                    "type": "string",
                    "enum": ["landscape", "portrait", "square"],
                    "description": "Canvas orientation of the target format.",
                },
                "min_width": {
                    "type": "integer",
                    "description": "Minimum image width in pixels (default 800).",
                },
            },
            "required": ["query"],
        },
    },
}

MIN_WIDTHS = {"square": 900, "landscape": 1000, "portrait": 800}


def _query_variants(query: str) -> list[str]:
    """Progressive simplifications of a too-specific query (long → short)."""
    q = query.strip()
    variants = [q]
    words = [w for w in re.split(r"\W+", q) if len(w) > 2]
    for n in (4, 3, 2):
        if len(words) > n:
            variant = " ".join(words[:n])
            if variant not in variants:
                variants.append(variant)
    return variants


# High-yield editorial fallbacks — used only when the LLM's query (and its
# simplified variants) return nothing, so an image slot still gets media.
_FALLBACK_QUERIES = [
    "minimalist architecture",
    "abstract paper texture",
    "city skyline fog",
    "natural stones",
    "light and shadow",
]


async def _fetch_variants(
    queries: list[str],
    orientation: str,
    min_w: int,
    limit: int,
) -> list[dict]:
    seen: dict[str, dict] = {}
    for variant in queries:
        for fn in (search_pexels, search_pixabay, search_wikimedia):
            try:
                cands = await fn(variant, orientation=orientation, per_page=max(6, limit))
            except Exception as e:  # noqa: BLE001
                log.warning("[photo] provider %s failed: %s", fn.__name__, e)
                continue
            for c in cands:
                if (c.get("width") or 0) >= min_w or (c.get("width") or 0) == 0:
                    seen.setdefault(c.get("url"), c)
        if seen:
            break  # a variant produced usable results — stop spending searches
    return list(seen.values())


async def search_photo_candidates(
    query: str,
    orientation: str = "landscape",
    min_width: int | None = None,
    limit: int = 8,
) -> list[dict]:
    """Search providers in order; return normalized candidates ([] if none).

    If a long/rare query returns nothing, it is retried with progressively
    simpler variants, then a small pool of high-yield editorial fallbacks, so
    an off-key phrase never sinks the whole post.
    """
    orientation = orientation if orientation in ("landscape", "portrait", "square") else "landscape"
    min_w = min_width or MIN_WIDTHS.get(orientation, 800)

    candidates = await _fetch_variants(_query_variants(query), orientation, min_w, limit)
    if candidates:
        return candidates
    return await _fetch_variants(_FALLBACK_QUERIES, orientation, min_w, limit)


def _attribution(c: dict) -> str:
    provider = c.get("provider", "")
    who = c.get("photographer") or ""
    lic = c.get("license") or ""
    if provider == "pexels":
        return f"Photo by {who} on Pexels" if who else "Photo via Pexels"
    if provider == "pixabay":
        return f"Photo by {who} on Pixabay" if who else "Photo via Pixabay"
    if provider == "wikimedia":
        bits = [who, lic] if who else [lic]
        bits = [b for b in bits if b]
        return "Wikimedia Commons · " + " · ".join(bits) if bits else "via Wikimedia Commons"
    return ""


def pick_best_candidate(
    candidates: list[dict], seed: str = ""
) -> dict | None:
    """Pick one vetted candidate (first usable, deterministic tie-break)."""
    if not candidates:
        return None
    best = candidates[0]
    for c in candidates[1:]:
        if (c.get("width") or 0) > (best.get("width") or 0):
            best = c
    out = dict(best)
    out["attribution"] = _attribution(best)
    return out


async def run_find_photo(args: dict) -> dict:
    """Execute a ``find_photo`` tool call → a single vetted candidate dict."""
    query = str(args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "empty query"}
    orientation = str(args.get("orientation") or "landscape")
    min_width = args.get("min_width")
    candidates = await search_photo_candidates(query, orientation, min_width)
    best = pick_best_candidate(candidates)
    if not best:
        return {"ok": False, "error": "no results", "query": query}
    return {"ok": True, **best}


# ---------------------------------------------------------------------------
# Download + embed
# ---------------------------------------------------------------------------

_AUTO_STYLE = (
    "<style>.auto-photo{position:relative;display:block;width:100%;height:100%}"
    ".auto-photo img{display:block;width:100%;height:100%;object-fit:cover;"
    "filter:grayscale(1) contrast(1.05)}"
    ".auto-photo .credit{position:absolute;bottom:6px;right:8px;"
    "font-family:var(--font-sans);font-size:10px;letter-spacing:.04em;"
    "text-transform:uppercase;color:var(--color-text-tertiary);"
    "background:var(--color-bg);padding:2px 6px}</style>"
)

_IMG_SLOT_RE = re.compile(r'<img\b[^>]*\bdata-image-key="(\d+)"[^>]*>', re.IGNORECASE)
_EL_SLOT_RE = re.compile(r'<([a-z][\w-]*)\b[^>]*\bdata-image-key="(\d+)"[^>]*>', re.IGNORECASE)


_UA = "Tasbir/1.0 (https://github.com/sapienskid/tasbir; media pipeline)"


async def download_photo(candidate: dict) -> dict | None:
    """SSRF-guarded download of a photo candidate → base64 + mime (or None)."""
    url = candidate.get("url", "")
    if not url:
        return None
    settings = get_settings()
    try:
        check_image_url(url)
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            max_redirects=settings.image_max_redirects,
            headers={"User-Agent": _UA},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        if ctype and not ctype.startswith("image/"):
            return None
        raw = resp.content
        if len(raw) > settings.image_max_bytes:
            log.warning("[photo] %s exceeds %d-byte cap", url, settings.image_max_bytes)
            return None
        return {
            "data": base64.b64encode(raw).decode("ascii"),
            "mime": ctype or "image/jpeg",
            "alt": candidate.get("photographer") or "",
        }
    except Exception as e:  # noqa: BLE001
        log.warning("[photo] download failed %s: %s", url, e)
        return None


def embed_photo_into_html(html: str, image: dict, credit: str) -> str:
    """Fill the first ``data-image-key`` marker with a grayscale photo + credit.

    For ``<img data-image-key="N">`` markers (the template/designer norm) the
    surrounding slot element is preserved and only the ``<img>`` is replaced, so
    the template's own box sizing keeps working. The credit overlays the image's
    bottom-right corner; a guard style is injected once.
    """
    b64 = image.get("data", "")
    mime = image.get("mime", "image/jpeg")
    alt = html_lib.escape(image.get("alt", "") or "", quote=True)
    cred = html_lib.escape(credit or "", quote=True)
    src = f"data:{mime};base64,{b64}"
    img_markup = (
        f'<span class="auto-photo">'
        f'<img src="{src}" alt="{alt}" />'
        f'<span class="credit">{cred}</span></span>'
    )

    replaced = _IMG_SLOT_RE.sub(lambda m: img_markup, html, count=1)
    if replaced is html:
        # Non-<img> element with the marker (rare) → replace the element itself.
        replaced = _EL_SLOT_RE.sub(
            lambda m: f'<figure class="auto-photo">{img_markup}</figure>', html, count=1
        )
    if replaced is html:
        return html
    if "<head>" in replaced:
        return replaced.replace("<head>", f"<head>{_AUTO_STYLE}", 1)
    return _AUTO_STYLE + replaced
