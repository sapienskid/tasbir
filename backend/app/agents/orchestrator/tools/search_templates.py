"""Tool: Search for existing HTML templates to use as a base for generation."""

from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated


async def search_templates(
    state: Annotated[dict, InjectedState],
    query: str,
) -> str:
    """Search for existing templates matching the content type or format.

    Call this when you need to find a template to use as a starting point
    for a new design.

    Args:
        query: Search keywords (e.g., 'instagram quote', 'linkedin article').

    Returns:
        Template HTML and metadata if found, or a message saying none exist.
    """
    templates = state.get("templates", [])

    if templates:
        results = []
        query_lower = query.lower()
        for t in templates:
            name = t.get("name", "").lower()
            desc = t.get("description", "").lower()
            if query_lower in name or query_lower in desc:
                results.append(f"Template: {t['name']}\n{t.get('html', '')[:200]}...")

        if results:
            return "\n---\n".join(results[:3])

    return "No matching templates found. Generate a fresh design from scratch."
