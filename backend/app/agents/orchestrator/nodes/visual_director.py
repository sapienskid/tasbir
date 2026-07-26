"""Visual Director agent (Elena Rostova) — chooses background style per format in parallel.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() so the model
can dynamically decide whether to generate a CSS background or search
Unsplash for a photo.
"""

import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.agents.orchestrator.state import GenerationState
from app.agents.orchestrator.tools.generate_background import generate_background_tool
from app.agents.orchestrator.tools.search_unsplash import search_unsplash
from app.agents.prompts.registry import get_prompt
from app.services.formats import get_format_info
from app.services.llm import call_llm_with_retry, get_llm

_tools = [generate_background_tool, search_unsplash]
_tool_node = ToolNode(_tools)


async def _generate_bg_for_format(
    fmt_id: str,
    state: GenerationState,
    system_prompt: str,
    brand_primary: str,
    brand_secondary: str,
) -> tuple[str, dict[str, str]]:
    fmt_info = await get_format_info(fmt_id)
    llm = get_llm(agent_role="visual_director", temperature=0.4, max_tokens=800).bind_tools(_tools)
    brand = state.get("brand", {})
    mood = _determine_mood(fmt_info.id, brand)
    copy_snippet = state.get("copy_by_format", {}).get(fmt_id, "")[:400]

    user_content = (
        f"FORMAT: {fmt_info.name} ({fmt_info.id})\n"
        f"CANVAS DIMENSIONS: {fmt_info.width}x{fmt_info.height}\n"
        f"FORMAT INSTRUCTION: {fmt_info.ai_instruction}\n"
        f"BRAND: {brand.get('name', '')} — Tone: {brand.get('tone', 'professional')}\n"
        f"TITLE: {state.get('title', '')}\n"
        f"ARTICLE CONTEXT (the graphic must visually reflect this subject):\n{state.get('content', '')[:800]}\n\n"
        f"STRATEGIC BRIEF SNIPPET: {state.get('strategic_brief', '')[:600]}\n"
        f"COPY SNIPPET (IF AVAILABLE): {copy_snippet}\n"
        f"MOOD: {mood}\n"
        f"BRAND PRIMARY COLOR: {brand_primary}\n"
        f"BRAND SECONDARY COLOR: {brand_secondary}\n\n"
        f"Select the perfect background aesthetic for this visual graphic canvas that matches the {brand.get('name', brand.get('tone', 'professional'))} brand identity. "
        f"The background must visually support the article topic described above. "
        f"Call search_unsplash or generate_background_tool."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = await call_llm_with_retry(llm, messages)

    if response.tool_calls:
        tool_result = await _tool_node.ainvoke({"messages": [response]})
        css_line = None
        name_line = None
        for msg in tool_result.get("messages", []):
            if isinstance(msg, ToolMessage) and msg.content:
                for line in str(msg.content).split("\n"):
                    if line.startswith("CSS:"):
                        css_line = line.replace("CSS: ", "")
                    elif line.startswith("Background:"):
                        name_line = line.replace("Background: ", "")
                    elif line.startswith("Photo URL:"):
                        css_line = f"background: url({line.replace('Photo URL: ', '')}) center/cover no-repeat;"
                        name_line = "unsplash"

        bg_dict = {
            "css": css_line or f"background-color: {brand_primary};",
            "name": name_line or "generated",
        }
    else:
        from app.services.backgrounds import generate_background

        bg = generate_background(
            content_type="article",
            mood=mood,
            brand_primary=brand_primary,
            brand_secondary=brand_secondary,
        )
        bg_dict = {"css": bg.css, "name": bg.name}

    return fmt_id, bg_dict


async def visual_director_node(state: GenerationState) -> dict:
    prompt = await get_prompt("visual_director")
    brand = state.get("brand", {})
    tokens = state.get("design_tokens", {})

    brand_primary = (
        brand.get("primary_color")
        or tokens.get("color", {}).get("primary", {}).get("$value")
        or "#667eea"
    )
    brand_secondary = (
        brand.get("secondary_color")
        or tokens.get("color", {}).get("secondary", {}).get("$value")
        or "#764ba2"
    )

    formats = state["requested_formats"]
    tasks = [
        _generate_bg_for_format(fmt, state, prompt.system_prompt, brand_primary, brand_secondary)
        for fmt in formats
    ]
    results = await asyncio.gather(*tasks)

    backgrounds = {fmt: bg for fmt, bg in results}
    return {"background_by_format": backgrounds}


def _determine_mood(format_name: str, brand: dict) -> str:
    brand_tone = brand.get("tone", "professional")
    mood_map = {
        "instagram-story": "story",
        "carousel-post": "story",
        "pinterest-pin": "minimal",
        "twitter-card": "energetic",
        "linkedin-post": "professional",
    }
    format_mood = mood_map.get(format_name)
    if format_mood and brand_tone in ("minimal", "monochrome", "black-white", "neutral"):
        return brand_tone
    return format_mood or brand_tone
