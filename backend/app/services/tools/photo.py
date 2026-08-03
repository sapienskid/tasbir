"""``find_photo`` / ``choose_photo`` — LLM-driven stock photo search.

``find_photo`` returns a **shortlist** of candidates (provider fallback order
Pexels → Pixabay → Wikimedia; unkeyed providers skipped) as the tool result the
model sees. The model then calls ``choose_photo`` to pick one — or re-calls
``find_photo`` with a refined query. Nothing is picked deterministically by the
pipeline, and there is no generic fallback query pool: a search that finds
nothing simply reports "no results" and the LLM decides what to do next.

Download → base64 → inject happens in the pipeline via
:func:`download_photo` / :func:`embed_photo_into_html`.
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
            "Search royalty-free stock photos for the post and return a numbered "
            "shortlist of candidates. Then call choose_photo with the index of "
            "the best fit, or call find_photo again with a REFINED query if none "
            "fit. Use SHORT, BROAD queries (1-3 words, e.g. 'minimal architecture' "
            "'paper texture') — long phrases rarely match. The photo is shown "
            "grayscale and credited on the post."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A SHORT, BROAD search query (1-3 words) matching the "
                        "post's subject, e.g. 'minimal typography', 'city fog', "
                        "'paper texture'. Avoid long descriptive phrases."
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

CHOOSE_PHOTO_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "choose_photo",
        "description": (
            "Pick the best photo from the find_photo shortlist by index. Call "
            "exactly once after reviewing the candidates. If none fit, call "
            "find_photo again with a refined query instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "Index of the chosen candidate from the shortlist.",
                },
                "query": {
                    "type": "string",
                    "description": "Optional refined query if the pick was weak (unused when index is valid).",
                },
            },
            "required": ["index"],
        },
    },
}

MIN_WIDTHS = {"square": 900, "landscape": 1000, "portrait": 800}


async def search_photo_candidates(
    query: str,
    orientation: str = "landscape",
    min_width: int | None = None,
    limit: int = 8,
) -> list[dict]:
    """Search providers directly for the exact query; return normalized candidates.

    Providers are tried in fallback order until one yields usable results.
    No query rewriting, no generic fallback pool — a miss reports "no results"
    so the LLM can refine its own query.
    """
    orientation = orientation if orientation in ("landscape", "portrait", "square") else "landscape"
    min_w = min_width or MIN_WIDTHS.get(orientation, 800)

    seen: dict[str, dict] = {}
    for fn in (search_pexels, search_pixabay, search_wikimedia):
        try:
            cands = await fn(query, orientation=orientation, per_page=max(6, limit))
        except Exception as e:  # noqa: BLE001
            log.warning("[photo] provider %s failed: %s", fn.__name__, e)
            continue
        for c in cands:
            if (c.get("width") or 0) >= min_w or (c.get("width") or 0) == 0:
                seen.setdefault(c.get("url"), c)
        if seen:
            break  # first provider with usable results wins
    return list(seen.values())[:limit]


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


def format_shortlist(candidates: list[dict]) -> str:
    """Human/machine-readable shortlist text shown to the LLM after find_photo."""
    if not candidates:
        return (
            "No photos found for that query. Try ONE simpler, broader query "
            "(1-3 words). If that also finds nothing, decline media — do not keep "
            "refining."
        )
    lines = ["Photo candidates (pick one via choose_photo):"]
    for i, c in enumerate(candidates):
        dims = f"{c.get('width') or '?'}x{c.get('height') or '?'}"
        lines.append(
            f"[{i}] provider={c.get('provider')} · {dims} · license={c.get('license') or '?'} "
            f"· credit={_attribution(c)}"
        )
    lines.append("Reply by calling choose_photo with the best index — or find_photo with a refined query if none fit.")
    return "\n".join(lines)


def pick_candidate(candidates: list[dict], index) -> dict | None:
    """Return the candidate at ``index`` (validated) with attribution attached."""
    if not candidates or index is None:
        return None
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= len(candidates):
        return None
    out = dict(candidates[idx])
    out["attribution"] = _attribution(out)
    return out


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
