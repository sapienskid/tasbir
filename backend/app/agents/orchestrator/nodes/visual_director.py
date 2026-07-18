"""Visual Director agent — chooses background style per format.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() so the model
can dynamically decide whether to generate a CSS background or search
Unsplash for a photo.
"""

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.agents.orchestrator.state import GenerationState
from app.agents.orchestrator.tools.generate_background import generate_background_tool
from app.agents.orchestrator.tools.search_unsplash import search_unsplash
from app.agents.prompts.registry import get_prompt
from app.services.llm import get_llm

_tools = [generate_background_tool, search_unsplash]
_tool_node = ToolNode(_tools)


async def visual_director_node(state: GenerationState) -> dict:
    prompt = await get_prompt("visual_director")
    tokens = state.get("design_tokens", {})
    brand_primary = tokens.get("color", {}).get("primary", {}).get("$value", "#667eea")
    brand_secondary = tokens.get("color", {}).get("secondary", {}).get("$value", "#764ba2")

    llm = get_llm(agent_role="visual_director", temperature=0.3, max_tokens=800).bind_tools(_tools)
    backgrounds: dict[str, dict[str, str]] = {}

    for fmt in state["requested_formats"]:
        mood = _determine_mood(fmt, state.get("brand", {}))
        messages = [
            SystemMessage(content=prompt.system_prompt),
            HumanMessage(
                content=(
                    f"Format: {fmt}\n"
                    f"Copy: {state['copy_by_format'].get(fmt, '')[:500]}\n"
                    f"Mood: {mood}\n"
                    f"Brand primary: {brand_primary}\n"
                    f"Brand secondary: {brand_secondary}\n\n"
                    f"Choose a background. Call search_unsplash or generate_background_tool."
                )
            ),
        ]

        response = await llm.ainvoke(messages)

        if response.tool_calls:
            tool_result = await _tool_node.ainvoke({"messages": [response]})
            for msg in tool_result["messages"]:
                if isinstance(msg, ToolMessage) and msg.content:
                    css_line = None
                    name_line = None
                    for line in str(msg.content).split("\n"):
                        if line.startswith("CSS:"):
                            css_line = line.replace("CSS: ", "")
                        elif line.startswith("Background:"):
                            name_line = line.replace("Background: ", "")
                        elif line.startswith("Photo URL:"):
                            css_line = f"background: url({line.replace('Photo URL: ', '')}) center/cover no-repeat;"
                            name_line = "unsplash"
                    backgrounds[fmt] = {
                        "css": css_line or f"background-color: {brand_primary};",
                        "name": name_line or "generated",
                    }
        else:
            # Model responded with text directly — use a default gradient
            from app.services.backgrounds import generate_background

            bg = generate_background(content_type=mood, mood=mood, brand_primary=brand_primary, brand_secondary=brand_secondary)
            backgrounds[fmt] = {"css": bg.css, "name": bg.name}

    return {"background_by_format": backgrounds, "next_node": "designer"}


def _determine_mood(format_name: str, brand: dict) -> str:
    brand_tone = brand.get("tone", "professional")
    mood_map = {
        "instagram-story": "story",
        "carousel-post": "story",
        "pinterest-pin": "minimal",
        "twitter-card": "energetic",
        "linkedin-post": "professional",
        "facebook-post": "warm",
    }
    return mood_map.get(format_name, brand_tone)
