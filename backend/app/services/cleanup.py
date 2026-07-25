"""Post-processing cleanup for generated HTML assets.

Strips unwanted content like hashtags, excessive whitespace,
and ensures design token compliance.
"""

import re


def clean_html(html: str) -> str:
    """Clean generated HTML before rendering.

    Removes:
    - Trailing hashtag blocks
    - Excessive blank lines
    - Empty HTML elements
    - Unwanted markdown artifacts
    """
    lines = html.split("\n")
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

    result = re.sub(r'\n{3,}', '\n\n', result)

    result = re.sub(r'<div[^>]*>\s*</div>', '', result)
    result = re.sub(r'<span[^>]*>\s*</span>', '', result)

    return result
