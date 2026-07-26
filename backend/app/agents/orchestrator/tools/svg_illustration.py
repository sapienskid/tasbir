"""SVG illustration tool — generates vector graphics using Gemini Flash Lite.

Called by the designer when the layout needs custom illustration.
Has a 15 RPM rate limit aware retry mechanism.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from app.services.llm import call_llm_with_retry, get_llm

_RATE_LIMIT = 15  # RPM


@tool
async def svg_illustration(
    topic: str,
    style: str = "geometric",
    width: int = 1080,
    height: int = 600,
) -> str:
    """Generate an SVG illustration for a social media graphic.

    Call this when the design needs custom vector artwork — icons,
    geometric patterns, abstract compositions, or data visuals.
    Returns raw SVG markup ready for embedding in HTML.

    Args:
        topic: What the illustration should depict (e.g. 'quantum entanglement', 'network nodes')
        style: Visual style — 'geometric', 'abstract', 'minimal', 'tech', 'organic'
        width: Canvas width in pixels
        height: Canvas height in pixels
    """
    llm = get_llm(agent_role="illustrator", temperature=0.3, max_tokens=4096)
    system = (
        "You are a vector illustration specialist. Create clean, production-ready SVG graphics. "
        "Output ONLY the raw <svg>...</svg> markup with no additional text or markdown."
    )
    user = (
        f"Illustration topic: {topic}\n"
        f"Style: {style}\n"
        f"Dimensions: {width}x{height}\n"
        f"viewBox=\"0 0 {width} {height}\"\n"
        f"Use geometric shapes, clean lines, and subtle gradients. "
        f"No text labels. Keep under 8KB."
    )

    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = await call_llm_with_retry(llm, messages, max_retries=3)

    raw = response.content
    if isinstance(raw, list):
        texts = []
        for b in raw:
            if isinstance(b, str):
                texts.append(b)
            elif isinstance(b, dict) and b.get("type") == "text":
                texts.append(b.get("text", ""))
        raw = "".join(texts)

    return _extract_svg(str(raw))


def _extract_svg(text: str) -> str:
    text = text.strip()
    if text.startswith("```svg"):
        text = text[6:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    if "<svg" in text:
        start = text.index("<svg")
        end = text.rindex("</svg>") + 6
        text = text[start:end]
    return text.strip()
