"""Visual Director agent — chooses background style per format.

Input:  copy_by_format, design_tokens, brand
Output: background_by_format (dict of format → background style)
"""

from app.agents.orchestrator.state import GenerationState
from app.services.llm import call_llm
from app.services.backgrounds import generate_background
from app.agents.prompts.registry import get_prompt


async def visual_director_node(state: GenerationState) -> dict:
    prompt = await get_prompt("visual_director")
    tokens = state.get("design_tokens", {})
    brand_primary = (
        tokens.get("color", {}).get("primary", {})
        .get("$value", "#667eea")
    )
    brand_secondary = (
        tokens.get("color", {}).get("secondary", {})
        .get("$value", "#764ba2")
    )

    backgrounds: dict[str, dict[str, str]] = {}

    for fmt in state["requested_formats"]:
        mood = _determine_mood(fmt, state.get("brand", {}))

        # Use AI to refine background choice
        user_prompt = (
            f"Format: {fmt}\n"
            f"Copy: {state['copy_by_format'].get(fmt, '')[:500]}\n"
            f"Mood: {mood}\n"
            f"Brand primary: {brand_primary}\n"
            f"Brand secondary: {brand_secondary}\n\n"
            f"Choose: gradient, pattern, solid, or unsplash.\n"
            f"Output one word only."
        )

        style_choice = await call_llm(
            agent_role="visual_director",
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=20,
        )

        bg = generate_background(
            content_type=mood,
            mood=style_choice.strip().lower() or mood,
            brand_primary=brand_primary,
            brand_secondary=brand_secondary,
        )
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
