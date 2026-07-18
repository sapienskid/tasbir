"""Ghost Admin API client — fetches content from Ghost CMS.

Uses the Ghost Admin API with JWT token authentication.
Supports fetching published posts and converting to our internal format.
"""

import time

import httpx

from app.config import get_settings


def _generate_jwt(admin_api_key: str) -> str:
    """Generate a short-lived JWT for Ghost Admin API authentication.

    Ghost Admin API keys have format ``{id}:{secret}``.
    The JWT expires in 5 minutes (max allowed by Ghost).

    Args:
        admin_api_key: Ghost Admin API key (format: id:secret).

    Returns:
        Encoded JWT string.
    """
    import jwt as pyjwt

    parts = admin_api_key.split(":")
    if len(parts) != 2:
        msg = "Invalid Ghost Admin API key format. Expected 'id:secret'."
        raise ValueError(msg)

    key_id, secret = parts
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "aud": "/admin/",
    }
    return pyjwt.encode(payload, secret, algorithm="HS256", headers={"kid": key_id})


async def fetch_post(post_id: str) -> dict | None:
    """Fetch a single post by ID from Ghost.

    Args:
        post_id: Ghost post ID or slug.

    Returns:
        Post data dict with title, html, excerpt, tags, feature_image.
    """
    settings = get_settings()
    if not settings.ghost_url or not settings.ghost_admin_api_key:
        return None

    token = _generate_jwt(settings.ghost_admin_api_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.ghost_url}/ghost/api/admin/posts/{post_id}/",
                headers={"Authorization": f"Ghost {token}"},
                params={"include": "tags"},
            )
            response.raise_for_status()
            data = response.json()
            post = data.get("posts", [{}])[0]

            return {
                "title": post.get("title", ""),
                "html": post.get("html", ""),
                "excerpt": post.get("excerpt", ""),
                "feature_image": post.get("feature_image", ""),
                "url": f"{settings.ghost_url}/{post.get('slug', '')}",
                "tags": [t.get("name", "") for t in post.get("tags", [])],
            }
    except httpx.HTTPError as e:
        print(f"[ghost] Failed to fetch post {post_id}: {e}")
        return None


async def fetch_recent_posts(limit: int = 5) -> list[dict]:
    """Fetch recent published posts from Ghost.

    Args:
        limit: Maximum number of posts to return.

    Returns:
        List of post data dicts.
    """
    settings = get_settings()
    if not settings.ghost_url or not settings.ghost_admin_api_key:
        return []

    token = _generate_jwt(settings.ghost_admin_api_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.ghost_url}/ghost/api/admin/posts/",
                headers={"Authorization": f"Ghost {token}"},
                params={"limit": limit, "include": "tags"},
            )
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "id": post.get("id"),
                    "title": post.get("title", ""),
                    "excerpt": post.get("excerpt", ""),
                    "feature_image": post.get("feature_image", ""),
                    "url": f"{settings.ghost_url}/{post.get('slug', '')}",
                    "tags": [t.get("name", "") for t in post.get("tags", [])],
                    "published_at": post.get("published_at"),
                }
                for post in data.get("posts", [])
            ]
    except httpx.HTTPError as e:
        print(f"[ghost] Failed to fetch recent posts: {e}")
        return []
