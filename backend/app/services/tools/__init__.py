"""Media tools — LLM-callable tools the pipeline exposes to agents.

- ``find_photo``    — search stock photos (Pexels / Pixabay / Wikimedia)
- ``icon_search``   — deterministic search over the vendored Lucide library
- ``illustrate``    — unified illustration director (compose / procedural / DiceBear)

See :mod:`app.services.tools.photo`, :mod:`app.services.tools.icon_search`,
and :mod:`app.services.tools.illustrator`.
"""

from app.services.tools.icon_search import ICON_SEARCH_TOOL, search_icons
from app.services.tools.illustrator import ILLUSTRATE_TOOL, compose_peep, run_illustrate
from app.services.tools.photo import (
    CHOOSE_PHOTO_TOOL,
    FIND_PHOTO_TOOL,
    download_photo,
    embed_photo_into_html,
    format_shortlist,
    pick_candidate,
    search_photo_candidates,
)

# Every tool bound to LLM calls that can produce media for a post.
MEDIA_TOOLS: list[dict] = [FIND_PHOTO_TOOL, CHOOSE_PHOTO_TOOL, ICON_SEARCH_TOOL, ILLUSTRATE_TOOL]

__all__ = [
    "FIND_PHOTO_TOOL",
    "CHOOSE_PHOTO_TOOL",
    "ICON_SEARCH_TOOL",
    "ILLUSTRATE_TOOL",
    "MEDIA_TOOLS",
    "search_photo_candidates",
    "search_icons",
    "format_shortlist",
    "pick_candidate",
    "download_photo",
    "embed_photo_into_html",
    "compose_peep",
    "run_illustrate",
]
