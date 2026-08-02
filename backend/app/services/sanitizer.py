"""HTML sanitizer — removes executable / dangerous content from untrusted HTML.

Two modes:

- ``strict`` (default): for LLM-produced designer HTML. Drops scripts, frames,
  forms, external links, event handlers, and dangerous URL schemes. The
  pipeline re-injects Google Fonts, KaTeX, and images afterwards, so nothing
  legitimate is lost.
- ``preserve_system``: for operator-edited HTML in the rerender endpoint,
  where KaTeX/Mermaid/font CDN tags injected by the system must survive.
  Only known CDN scripts are allowed; everything else dangerous is dropped.

CSS ``<style>`` blocks are always kept (the design system depends on them),
but ``url(javascript:)``/``expression()`` payloads are scrubbed.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from html.parser import HTMLParser

log = logging.getLogger(__name__)

_DROP_TAGS_STRICT = {
    "script", "iframe", "object", "embed", "base", "form", "input", "button",
    "textarea", "select", "option", "link", "meta",
}

# In preserve_system mode these tags are still dropped, but <script>/<link>
# are allowed when their src/href is a trusted CDN.
_DROP_TAGS_PRESERVE = {"iframe", "object", "embed", "base", "form", "input", "button",
                       "textarea", "select", "option", "meta"}

_TRUSTED_CDNS = (
    "https://cdn.jsdelivr.net/",
    "https://unpkg.com/",
    "https://mermaid.js.org/",
    "https://fonts.googleapis.com/",
    "https://fonts.gstatic.com/",
)

_DANGEROUS_SCHEMES = re.compile(r"^\s*(?:javascript|vbscript|data:text/html|file):", re.IGNORECASE)

# Void elements have no content or end tag — dropping one must not enter
# skip mode, or everything after it would be discarded.
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

_CSS_PAYLOADS = re.compile(
    r"url\s*\(\s*(['\"]?)\s*(javascript|data:text/html|file):", re.IGNORECASE
)
_CSS_EXPRESSION = re.compile(r"expression\s*\(", re.IGNORECASE)


def _keep_attr(name: str, value: str, mode: str) -> bool:
    if name.lower().startswith("on"):
        return False
    low = value.strip().lower()
    if _DANGEROUS_SCHEMES.search(low):
        return False
    return True


def _clean_attr(name: str, value: str) -> str:
    value = html_lib.escape(value, quote=True)
    return f'{name}="{value}"'


class _Sanitizer(HTMLParser):
    def __init__(self, mode: str = "strict"):
        super().__init__(convert_charrefs=True)
        self.mode = mode
        self.out: list[str] = []
        self.skip_depth = 0

    def _should_drop_tag(self, tag: str, attrs: dict[str, str]) -> bool:
        if self.mode == "strict":
            return tag in _DROP_TAGS_STRICT
        if tag in _DROP_TAGS_PRESERVE:
            return True
        if tag == "script":
            src = attrs.get("src", "")
            return not any(src.startswith(cdn) for cdn in _TRUSTED_CDNS)
        if tag == "link":
            href = attrs.get("href", "")
            return not any(href.startswith(cdn) for cdn in _TRUSTED_CDNS)
        return False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth += 1
            return
        attr_map = {k.lower(): v or "" for k, v in attrs}
        if self._should_drop_tag(tag, attr_map):
            # Void elements have no content to skip; just drop them.
            if tag not in _VOID_TAGS:
                self.skip_depth = 1
            return
        clean = [(k, v) for k, v in attr_map.items() if _keep_attr(k, v, self.mode)]
        if clean:
            self.out.append(f"<{tag} " + " ".join(_clean_attr(k, v) for k, v in clean) + ">")
        else:
            self.out.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_depth:
            return
        attr_map = {k.lower(): v or "" for k, v in attrs}
        if self._should_drop_tag(tag, attr_map):
            return
        clean = [(k, v) for k, v in attr_map.items() if _keep_attr(k, v, self.mode)]
        if clean:
            self.out.append(f"<{tag} " + " ".join(_clean_attr(k, v) for k, v in clean) + "/>")
        else:
            self.out.append(f"<{tag}/>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in _VOID_TAGS:
            return  # stray void end tags are meaningless
        if self.mode == "strict" and tag in _DROP_TAGS_STRICT:
            return
        if self.mode != "strict" and tag in _DROP_TAGS_PRESERVE:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.out.append(data)

    def handle_comment(self, data: str) -> None:
        if self.skip_depth:
            return
        self.out.append(f"<!--{data}-->")

    def handle_pi(self, data: str) -> None:
        if self.skip_depth:
            return
        self.out.append(f"<?{data}>")

    def handle_decl(self, decl: str) -> None:
        self.out.append(f"<!{decl}>")

    def result(self) -> str:
        return "".join(self.out)


def _scrub_css(html: str) -> str:
    html = _CSS_PAYLOADS.sub("url($1about:blank)", html)
    html = _CSS_EXPRESSION.sub("nope(", html)
    return html


def sanitize_html(html: str, mode: str = "strict") -> str:
    """Return a sanitized copy of the input HTML."""
    if not html:
        return html
    parser = _Sanitizer(mode=mode)
    try:
        parser.feed(html)
        parser.close()
    except Exception as e:  # malformed input — never let it through unsanitized
        log.warning("[sanitizer] parse failed (%s); returning empty document", e)
        return ""
    out = parser.result()
    return _scrub_css(out)


__all__ = ["sanitize_html"]
