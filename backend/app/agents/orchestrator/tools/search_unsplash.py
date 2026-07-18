"""Tool: Search Unsplash for free stock photos."""

from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

from app.services.unsplash import search_photo


async def search_unsplash(
    state: Annotated[dict, InjectedState],
    query: str,
) -> str:
    """Search for free stock photos on Unsplash.

    Use this when a design needs a photographic background. The image
    is free to use with attribution.

    Args:
        query: Search terms describing the desired photo.

    Returns:
        Image URL and attribution text, or a message saying no photo was found.
    """
    url = await search_photo(query)
    if url:
        return (
            f"Photo URL: {url}\n"
            f"Attribution: Photo from Unsplash (free to use with attribution)"
        )
    return "No photo found. Use a CSS gradient or pattern background instead."
