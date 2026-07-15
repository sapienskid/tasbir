"""Unsplash API client — free stock photo backgrounds.

Demo mode: 50 requests/hour
After production approval: 1,000 requests/hour
Image URLs don't count against rate limit (only API calls do).

Requires UNSPLASH_ACCESS_KEY in environment.
"""

import httpx

from app.config import get_settings

UNSPLASH_API = "https://api.unsplash.com"


async def search_photo(query: str, orientation: str = "squarish") -> str | None:
    """Search for a free stock photo matching the query.

    Args:
        query: Search term (e.g., "technology", "nature", "business")
        orientation: landscape, portrait, or squarish

    Returns:
        Regular-sized image URL (1080px width), or None if no results.
        The URL is hotlinkable directly from Unsplash's CDN.
    """
    settings = get_settings()
    if not settings.unsplash_access_key:
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{UNSPLASH_API}/search/photos",
            params={
                "query": query,
                "per_page": 1,
                "orientation": orientation,
                "content_filter": "high",
            },
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data.get("results"):
            return None

        return data["results"][0]["urls"]["regular"]


async def random_photo(
    query: str = "",
    orientation: str = "squarish",
) -> str | None:
    """Get a random photo, optionally filtered by search term."""
    settings = get_settings()
    if not settings.unsplash_access_key:
        return None

    params = {"orientation": orientation, "content_filter": "high"}
    if query:
        params["query"] = query

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{UNSPLASH_API}/photos/random",
            params=params,
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        return data.get("urls", {}).get("regular")
