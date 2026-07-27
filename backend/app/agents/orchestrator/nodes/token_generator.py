"""Token Generator agent (Dr. Soren Lindqvist) — generates full-spectrum DTCG design tokens.

Follows the same pattern as designer/visual_director nodes:
  get_llm().bind_tools() → call_llm_with_retry → ToolNode → final response

Tools available:
  - generate_colors_tool: Accessible color palette with contrast validation
  - generate_typography_tool: Complete typography scale  
  - generate_spacing_tool: Spacing scale
  - generate_borders_tool: Border radius + box shadows
  - check_contrast_tool: Validate WCAG contrast for any color pair
"""

import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from app.agents.orchestrator.tools import (
    check_contrast_tool,
    generate_colors_tool,
    generate_typography_tool,
    generate_spacing_tool,
    generate_borders_tool,
)
from app.services.llm import call_llm_with_retry, get_llm

log = logging.getLogger(__name__)

_tools = [
    generate_colors_tool,
    generate_typography_tool,
    generate_spacing_tool,
    generate_borders_tool,
    check_contrast_tool,
]
_tool_node = ToolNode(_tools)


async def generate_tokens(
    brand_name: str,
    brand_description: str = "",
    tone: str = "professional",
    primary_color: str = "",
    secondary_color: str = "",
    accent_color: str = "",
) -> dict:
    """Generate a complete, full-spectrum design token set using LangChain tools.

    The agent:
    1. Reads brand context, calls generate_colors_tool for color palette
    2. Calls generate_typography_tool for typography
    3. Calls generate_spacing_tool for spacing
    4. Calls generate_borders_tool for radius + shadows
    5. Calls check_contrast_tool to validate text-on-background contrast
    6. Assembles all tool results into the final DTCG token set
    """

    llm = get_llm(
        agent_role="token_generator",
        temperature=0.3,
        max_tokens=8192,
    ).bind_tools(_tools)

    system = (
        "You are Dr. Soren Lindqvist, Design System Architect.\n\n"
        "Your mission: generate a COMPLETE FULL-SPECTRUM design token set.\n"
        "You have tools for each design system part — USE THEM.\n\n"
        "WORKFLOW:\n"
        "1. Call `generate_colors_tool` with primary/secondary/accent to get colors\n"
        "2. Call `generate_typography_tool` with the brand style to get typography\n"
        "3. Call `generate_spacing_tool` to get spacing scale\n"
        "4. Call `generate_borders_tool` to get border radius + shadows\n"
        "5. Review the results. If any color pairs fail contrast, adjust.\n"
        "6. Call `check_contrast_tool` to verify text-on-background pairs\n"
        "7. Assemble everything into the final DTCG JSON token set.\n\n"
        "OUTPUT STRUCTURE:\n"
        "{\n"
        '  "color": {...from generate_colors_tool...},\n'
        '  "typography": {...from generate_typography_tool...},\n'
        '  "spacing": {...from generate_spacing_tool...},\n'
        '  "borderRadius": {...from generate_borders_tool...},\n'
        '  "boxShadow": {...from generate_borders_tool...},\n'
        '  "opacity": {...standard opacity scale...}\n'
        "}\n\n"
        "Use \"$value\" and \"$type\" keys for all tokens.\n"
        "Return ONLY valid JSON inside ```json ... ``` fences."
    )

    user = (
        f"Brand: {brand_name}\n"
        f"Description: {brand_description or 'Professional design brand'}\n"
        f"Tone: {tone}\n"
        f"Primary color: {primary_color or 'auto-generate'}\n"
        f"Secondary color: {secondary_color or 'auto-generate'}\n"
        f"Accent color: {accent_color or '#6366F1'}\n\n"
        f"Call each design system tool to generate tokens, "
        f"then assemble the final DTCG JSON."
    )

    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    max_rounds = 8
    round_num = 0
    response = await call_llm_with_retry(llm, messages, agent_role="token_generator")

    while response.tool_calls and round_num < max_rounds:
        round_num += 1
        log.info("Token generator tool call round %d/%d", round_num, max_rounds)
        tool_result = await _tool_node.ainvoke({"messages": [response]})
        messages.append(response)
        for m in tool_result["messages"]:
            messages.append(m)
        if round_num < max_rounds:
            messages.append(HumanMessage(
                content="Review the tool outputs above. If more tools are needed, "
                        "call them. Otherwise, assemble the final DTCG token set as JSON."
            ))
            response = await call_llm_with_retry(llm, messages, agent_role="token_generator")

    raw = response.content
    if isinstance(raw, list):
        texts = []
        for b in raw:
            if isinstance(b, str):
                texts.append(b)
            elif isinstance(b, dict) and b.get("type") == "text":
                texts.append(b.get("text", ""))
        raw = "".join(texts)

    cleaned = str(raw).strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error("Token generator output is not valid JSON: %s", e)
        raise ValueError(f"LLM output was not valid JSON: {e}") from e
