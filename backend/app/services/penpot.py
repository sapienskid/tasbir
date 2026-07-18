"""Penpot MCP client — reads/writes design tokens and interacts with Penpot.

Penpot is an open-source design tool that exposes an MCP (Model Context
Protocol) server for programmatic access to design tokens and files.
"""

from app.config import get_settings


async def fetch_tokens() -> dict | None:
    """Fetch design tokens from Penpot via MCP.

    Returns:
        DTCG-format token dictionary, or None if unavailable.
    """
    import httpx

    settings = get_settings()
    if not settings.penpot_access_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.penpot_url}/api/mcp/tokens",
                headers={"Authorization": f"Bearer {settings.penpot_access_token}"},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"[penpot] Failed to fetch tokens: {e}")
        return None


async def push_tokens(tokens: dict) -> bool:
    """Push design tokens to Penpot.

    Args:
        tokens: DTCG-format token dictionary.

    Returns:
        True if successful.
    """
    import httpx

    settings = get_settings()
    if not settings.penpot_access_token:
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.put(
                f"{settings.penpot_url}/api/mcp/tokens",
                headers={"Authorization": f"Bearer {settings.penpot_access_token}"},
                json=tokens,
            )
            response.raise_for_status()
            return True
    except httpx.HTTPError as e:
        print(f"[penpot] Failed to push tokens: {e}")
        return False


async def export_file(file_id: str) -> dict | None:
    """Export a Penpot file as SVG.

    Args:
        file_id: Penpot file UUID.

    Returns:
        SVG data dict or None.
    """
    import httpx

    settings = get_settings()
    if not settings.penpot_access_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{settings.penpot_url}/api/mcp/files/{file_id}/export",
                headers={"Authorization": f"Bearer {settings.penpot_access_token}"},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"[penpot] Failed to export file {file_id}: {e}")
        return None
