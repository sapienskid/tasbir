"""Playwright render service — converts HTML to PNG via headless Chromium.

Communicates with the Playwright HTTP microservice running in Docker.
Waits for network idle (so Google Fonts CDN loads) and Mermaid diagrams
to finish rendering before capturing the screenshot.
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

    # Detect whether this page has Mermaid diagrams — if so, the renderer
    # must wait for the data-mermaid-ready sentinel before screenshotting.
    has_mermaid = "data-mermaid-ready" in html or "mermaid.run()" in html

    payload: dict = {
        "html": html,
        "width": width,
        "height": height,
        "format": "png",
        # Wait for network idle so Google Fonts CDN and Unsplash images load
        "wait_until": "networkidle",
    }

    if has_mermaid:
        # Ask the renderer to additionally wait for the Mermaid sentinel attribute
        payload["wait_for_selector"] = "body[data-mermaid-ready='true']"
        payload["wait_for_timeout"] = 3000  # max 3s extra after selector found

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{renderer_url}/render",
                json=payload,
            )
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as e:
        print(f"[renderer] Failed to render {format_id} ({width}x{height}): {e}")
        return None
