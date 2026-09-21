"""Hoist heavy inline image payloads out of a document (and put them back).

A post with an uploaded photo carries megabytes of base64 in its HTML. Every
structural pass over it (BeautifulSoup slot swap, the sanitizer's tokenizer,
slot extraction) is linear in that payload for no benefit — the payload is
opaque. ``hoist_data_uris`` swaps each big ``data:image/…;base64,`` payload for
a short unique token so those passes run on a few KB; ``restore_data_uris``
puts the originals back. This is what keeps the editor's instant preview fast
on image-heavy posts.
"""

from __future__ import annotations

import re
import uuid

_DATA_URI = re.compile(r"(data:image/[a-zA-Z0-9.+-]+;base64,)([A-Za-z0-9+/=]{512,})")


def hoist_data_uris(html: str) -> tuple[str, dict[str, str]]:
    """Replace big base64 image payloads with tokens → ``(light_html, table)``."""
    if not html or "base64," not in html:
        return html, {}
    nonce = uuid.uuid4().hex[:10]
    table: dict[str, str] = {}

    def _swap(m: re.Match) -> str:
        token = f"H{nonce}x{len(table)}x"
        table[token] = m.group(2)
        return m.group(1) + token

    return _DATA_URI.sub(_swap, html), table


def restore_data_uris(text: str, table: dict[str, str]) -> str:
    """Put hoisted payloads back into ``text`` (a document or one extracted value)."""
    for token, data in table.items():
        if token in text:
            text = text.replace(token, data)
    return text
