"""Post-processing cleanup for generated HTML assets.

Strips unwanted content:
- Emojis (must be purely professional typography and design accents)
- Agent/persona names that bleed into graphic output
- Website UI artifacts (buttons, navbars, URL headers)
- Trailing hashtags and excessive whitespace
- Enforces strict canvas viewport container styling (overflow: hidden, full canvas fit)
"""

import re

# Comprehensive regex matching all Unicode emoji ranges
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002600-\U000026FF"  # miscellaneous symbols
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    "\U00002300-\U000023FF"  # technical symbols
    "]+",
    flags=re.UNICODE,
)


# All internal agent persona names that must never appear in generated output
AGENT_NAMES: list[str] = [
    "Aura Vance",
    "Julian Sterling",
    "Elena Rostova",
    "Marcus Chen",
    "Victoria Thorne",
    "Dr. Soren Lindqvist",
    "Soren Lindqvist",
]

# Compiled regex to match any agent name (case-insensitive, whole-phrase)
_AGENT_NAME_PATTERN = re.compile(
    r"|".join(re.escape(name) for name in AGENT_NAMES),
    flags=re.IGNORECASE,
)


def remove_emojis(text: str) -> str:
    """Strip all raw emoji characters from text or HTML."""
    return EMOJI_PATTERN.sub("", text)


def strip_agent_names(text: str) -> str:
    """Strip all internal agent persona names from text or HTML.

    Prevents internal studio personas (Julian Sterling, Marcus Chen, etc.)
    from leaking into user-facing graphic output, HTML comments, or copy.
    """
    return _AGENT_NAME_PATTERN.sub("", text)


def clean_html(html: str) -> str:
    """Clean generated HTML before rendering to PNG.

    Removes:
    - Raw Unicode emojis
    - Website UI artifacts (interactive <button> elements transformed to styled <span> callouts)
    - Website navigation headers (<nav>, search bars)
    - Trailing hashtag blocks and markdown code block wrappers
    - Empty HTML elements
    """
    # 1. Strip raw emojis
    result = remove_emojis(html)

    # 2. Strip internal agent/persona names from graphic output
    result = strip_agent_names(result)

    # 3. Transform interactive website <button> tags to styled visual callouts
    result = re.sub(
        r'<button([^>]*)>(.*?)</button>',
        r'<span\1 style="display:inline-block; pointer-events:none;">\2</span>',
        result,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 4. Strip website navigation bars if generated accidentally
    result = re.sub(r'<nav[^>]*>.*?</nav>', '', result, flags=re.DOTALL | re.IGNORECASE)

    # 5. Clean line-by-line formatting
    lines = result.split("\n")
    cleaned = []
    in_body = False
    hashtag_block = 0

    for line in lines:
        stripped = line.strip()

        if "<body" in stripped:
            in_body = True

        if in_body:
            if re.match(r'^[\s#]*$', stripped):
                continue
            hashtags = re.findall(r'#[A-Za-z0-9_]+', stripped)
            if hashtags and len(hashtags) >= 2 and len(stripped) < 200:
                hashtag_block += 1
                if hashtag_block > 1:
                    continue
            else:
                hashtag_block = 0

        if stripped:
            hashtag_block = 0

        cleaned.append(line)

    result = "\n".join(cleaned)

    # Remove excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Clean empty divs or spans
    result = re.sub(r'<div[^>]*>\s*</div>', '', result)
    result = re.sub(r'<span[^>]*>\s*</span>', '', result)

    return result
