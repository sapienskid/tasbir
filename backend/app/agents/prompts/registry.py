"""Prompt registry — loads prompts from database with fallback to defaults.

Prompts are stored in the `prompt_registry` table and can be edited
via the API without redeploying the application.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptVersion:
    system_prompt: str
    user_template: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000


# Default prompts (used when DB is empty or prompt not found)
DEFAULT_PROMPTS: dict[str, PromptVersion] = {
    "strategist": PromptVersion(
        system_prompt=(
            "You are a content strategist. Analyze the provided content and "
            "determine its type, key message, target audience, and the best "
            "campaign angle for social media. Output a brief strategic plan."
        ),
        temperature=0.7,
        max_tokens=1000,
    ),
    "copywriter": PromptVersion(
        system_prompt=(
            "You are a social media copywriter. Write platform-native copy "
            "for the given format. Keep it concise, engaging, and specific. "
            "No filler, no generic statements. Each platform has its own voice."
        ),
        temperature=0.8,
        max_tokens=1500,
    ),
    "visual_director": PromptVersion(
        system_prompt=(
            "You are a visual director. Choose a background style for this "
            "post: gradient, pattern, solid color, or stock photo. "
            "Consider the brand's design tokens and content mood."
        ),
        temperature=0.6,
        max_tokens=800,
    ),
    "designer": PromptVersion(
        system_prompt=(
            "You are a social media designer. Generate a complete standalone "
            "HTML document for screenshot rendering. Use Tailwind CSS via CDN. "
            "Apply the provided design tokens. Ensure the design fits exactly "
            "within the specified dimensions. No overflow, no scrollbars."
        ),
        temperature=0.7,
        max_tokens=2500,
    ),
    "quality_check": PromptVersion(
        system_prompt=(
            "You are a quality assurance reviewer. Check the generated output "
            "for: text overflow, readability, brand compliance, contrast, "
            "and visual balance. Pass or fail with specific reasons."
        ),
        temperature=0.3,
        max_tokens=500,
    ),
    "token_generator": PromptVersion(
        system_prompt=(
            "You are a design token expert. Generate a complete set of design "
            "tokens in DTCG format based on the described brand identity. "
            "Include colors, typography, spacing, and border radius tokens."
        ),
        temperature=0.8,
        max_tokens=2000,
    ),
}


async def get_prompt(name: str) -> PromptVersion:
    """Get a prompt by name.

    Attempts to load from database first. Falls back to defaults
    if the prompt is not found in the registry.
    """
    # TODO: Load from prompt_registry table with caching
    prompt = DEFAULT_PROMPTS.get(name)
    if not prompt:
        msg = f"Unknown prompt: {name}. Available: {list(DEFAULT_PROMPTS.keys())}"
        raise ValueError(msg)
    return prompt


async def list_prompts() -> dict[str, PromptVersion]:
    """List all available prompts."""
    return dict(DEFAULT_PROMPTS)


async def update_prompt(name: str, system_prompt: str, **kwargs) -> PromptVersion:
    """Update or create a prompt. Creates a new version entry.

    Args:
        name: Prompt name (e.g., 'strategist', 'copywriter')
        system_prompt: New system prompt text
        **kwargs: Optional temperature, max_tokens, user_template

    Returns:
        The updated PromptVersion.
    """
    # TODO: Save to prompt_registry + create prompt_versions entry
    raise NotImplementedError("Database-backed prompt storage coming soon")
