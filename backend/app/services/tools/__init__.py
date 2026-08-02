"""Media tools — LLM-callable tools the pipeline exposes to agents.

- ``find_photo``    — search stock photos (Pexels / Pixabay / Wikimedia)
- ``illustrate``    — unified illustration director (Anthropic / CC0 kits)

See :mod:`app.services.tools.photo` and :mod:`app.services.tools.illustrator`.
"""

from app.services.tools.illustrator import ILLUSTRATE_TOOL, compose_handdrawn, run_illustrate
from app.services.tools.photo import (
    FIND_PHOTO_TOOL,
    download_photo,
    embed_photo_into_html,
    run_find_photo,
    search_photo_candidates,
)

# Every tool bound to LLM calls that can produce media for a post.
MEDIA_TOOLS: list[dict] = [FIND_PHOTO_TOOL, ILLUSTRATE_TOOL]

__all__ = [
    "FIND_PHOTO_TOOL",
    "ILLUSTRATE_TOOL",
    "MEDIA_TOOLS",
    "run_find_photo",
    "run_illustrate",
    "search_photo_candidates",
    "download_photo",
    "embed_photo_into_html",
    "compose_handdrawn",
]
