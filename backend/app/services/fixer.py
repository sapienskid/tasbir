"""Programmatic HTML fixer — automatically fixes common quality issues.

Runs after the designer generates HTML, before quality check audits it.
Each fix is deterministic (regex/string manipulation), not LLM-based.
"""

import re


def remove_template_placeholders(html: str) -> str:
    """Remove template syntax like {{variable}}, %s, [placeholder]."""
    orig = html
    html = re.sub(r"\{\{[^}]*\}\}", "", html, flags=re.DOTALL)
    html = re.sub(r"\{\{", "", html)
    html = re.sub(r"\}\}", "", html)
    html = re.sub(r"\{\s*\{", "", html)
    html = re.sub(r"\}\s*\}", "", html)
    html = re.sub(r"\[placeholder[^\]]*\]", "", html, flags=re.DOTALL)
    html = re.sub(r"%[sd]", "", html)
    html = re.sub(r"\[\[[^\]]*\]\]|<<[^>]*>>", "", html, flags=re.DOTALL)
    return html


def fix_canvas_overflow(html: str, width: int | None = None, height: int | None = None) -> str:
    """Fix overflow and viewport-unit issues in canvas HTML.

    - Replaces `min-h-screen` with exact pixel height or `h-full`
    - Ensures `overflow-hidden` on root container
    - Removes scroll-related CSS
    """
    body_style = f"width: {width}px; height: {height}px; overflow: hidden; margin: 0;"
    html = re.sub(
        r'<body[^>]*style\s*=\s*"[^"]*"[^>]*>',
        f'<body style="{body_style}">',
        html,
    )
    if '<body style="' not in html:
        body_style_alt = f"width: {width}px; height: {height}px; overflow: hidden; margin: 0"
        html = re.sub(r"<body([^>]*)>", f'<body style="{body_style_alt}"\\1>', html, count=1)

    html = re.sub(r"\bmin-h-screen\b", "h-full", html)
    html = re.sub(r"\bh-screen\b", "h-full", html)
    html = re.sub(r"\boverflow-y-auto\b", "overflow-hidden", html)
    html = re.sub(r"\boverflow-x-auto\b", "overflow-hidden", html)
    html = re.sub(r"\boverflow-scroll\b", "overflow-hidden", html)

    root_style_pattern = re.compile(
        r'(<(?:div|section|main)[^>]*style\s*=\s*"[^"]*)(overflow-[a-z]+)?([^"]*")'
    )
    html = root_style_pattern.sub(
        lambda m: m.group(1) + "overflow: hidden;" + m.group(3), html
    )

    return html


def strip_emojis(html: str) -> str:
    """Remove Unicode emojis from HTML text content.

    Emoji ranges cover most common emoji.
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # misc
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", html)


def fix_brand_colors(html: str, brand: dict | None = None) -> str:
    """Fill in missing brand color references in class names or CSS.

    Replaces generic color utility classes with brand-specific ones
    when the HTML uses template-like color references.
    """
    if not brand:
        return html

    primary = brand.get("primary_color", "#000000")
    secondary = brand.get("secondary_color", "#ffffff")

    color_map = {
        "primary": primary,
        "secondary": secondary,
        "accent": primary,
        "brand": primary,
    }

    for name, hex_color in color_map.items():
        html = re.sub(
            rf'class\s*=\s*"[^"]*\bbg-{name}\b[^"]*"',
            lambda m: m.group(0).replace(f"bg-{name}", ""),
            html,
        )
        html = html.replace(f"var(--color-{name})", hex_color)
        html = html.replace(f"var(--{name})", hex_color)

    return html


def fix_all(
    html: str,
    width: int | None = None,
    height: int | None = None,
    brand: dict | None = None,
) -> str:
    """Run all fixers in sequence on the given HTML."""
    html = remove_template_placeholders(html)
    html = strip_emojis(html)
    html = strip_interactive_elements(html)
    html = fix_canvas_overflow(html, width, height)
    html = fix_brand_colors(html, brand)
    html = _cleanup_whitespace(html)
    return html


def strip_interactive_elements(html: str) -> str:
    """Remove interactive elements that don't belong in a social media image.

    Strips: <a href> links, <button> elements, <input> elements,
    <select>, <textarea>, form tags, onclick handlers, and button-like CTA phrases.
    """
    html = re.sub(r'<a\b[^>]*>', '', html)
    html = re.sub(r'</a>', '', html)
    html = re.sub(r'<button\b[^>]*>.*?</button>', '', html, flags=re.DOTALL)
    html = re.sub(r'<input\b[^>]*/?>', '', html)
    html = re.sub(r'<select\b[^>]*>.*?</select>', '', html, flags=re.DOTALL)
    html = re.sub(r'<textarea\b[^>]*>.*?</textarea>', '', html, flags=re.DOTALL)
    html = re.sub(r'<form\b[^>]*>|</form>', '', html)
    html = re.sub(r'\bonclick\s*=\s*"[^"]*"', '', html)
    html = re.sub(r'cursor-pointer', '', html)

    # Strip button-like CTA text that appears in non-button HTML elements
    cta_patterns = re.compile(
        r'>\s*(Proceed\s+to\s+read(?:ing)?|Click\s+Here|Learn\s+More|Read\s+More|'
        r'Discover\s+More|Get\s+Started|Start\s+Now|Explore\s+Now|'
        r'Sign\s+Up|Subscribe|Download|Try\s+(?:It|Now|Free))\s*[<,\n]',
        re.IGNORECASE
    )
    html = cta_patterns.sub('>', html)
    return html


def _cleanup_whitespace(html: str) -> str:
    """Remove excessive blank lines left after placeholder removal."""
    html = re.sub(r"\n\s*\n\s*\n+", "\n\n", html)
    return html
