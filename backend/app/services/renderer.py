"""Playwright render service — converts HTML to PNG via headless Chromium.

Communicates with the Playwright HTTP microservice running in Docker.
"""

from app.config import get_settings


async def render_html(
    html: str,
    format_id: str = "default",
    width: int = 1080,
    height: int = 1080,
) -> bytes | None:
    """Send HTML to Playwright service and return PNG bytes.

    Args:
        html: Complete standalone HTML document.
        format_id: Output format identifier (for logging).
        width: Viewport width in pixels.
        height: Viewport height in pixels.

    Returns:
        PNG image bytes, or None if rendering failed.
    """
    import httpx

    settings = get_settings()
    renderer_url = getattr(settings, "renderer_url", "http://playwright:4000")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{renderer_url}/render",
                json={
                    "html": html,
                    "width": width,
                    "height": height,
                    "format": "png",
                },
            )
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as e:
        print(f"[renderer] Failed to render {format_id} ({width}x{height}): {e}")
        return None
