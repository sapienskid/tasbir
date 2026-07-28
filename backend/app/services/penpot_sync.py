"""Penpot API Sync Service — Direct, automated sync with self-hosted Penpot instance via REST/RPC API.

Uploads generated design files directly to Penpot via API (or MCP),
and fetches live Design Tokens from Penpot libraries automatically.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class PenpotAPISync:
    """Client for Penpot REST/RPC API automation."""

    def __init__(self, penpot_url: str | None = None, access_token: str | None = None):
        settings = get_settings()
        self.penpot_url = (penpot_url or getattr(settings, "penpot_url", "http://localhost:9001")).rstrip("/")
        self.token = access_token or getattr(settings, "penpot_access_token", "")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        return headers

    async def fetch_design_tokens(self) -> dict[str, str] | None:
        """Fetch live design tokens from Penpot instance via RPC API."""
        if not self.token:
            log.info("[penpot_sync] No Penpot token configured; using local design system tokens")
            return None

        url = f"{self.penpot_url}/api/rpc/command/get-all-tokens"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=self.headers, json={})
                if resp.status_code == 200:
                    data = resp.json()
                    log.info("[penpot_sync] Successfully fetched %d live tokens from Penpot", len(data))
                    return data
        except Exception as e:
            log.warning("[penpot_sync] Could not fetch live tokens from Penpot API: %s", e)

        return None

    async def auto_import_penpot_file(
        self,
        penpot_file_path: str | Path,
        project_id: str | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """Automatically upload/import a .penpot file into Penpot via API."""
        path = Path(penpot_file_path)
        if not path.exists():
            raise FileNotFoundError(f".penpot file not found: {path}")

        if not self.token:
            log.info("[penpot_sync] File generated at %s (Penpot token omitted, ready for UI import/MCP sync)", path)
            return {
                "status": "ready_local",
                "penpot_file_path": str(path),
                "message": "File generated successfully and saved to local output directory.",
            }

        url = f"{self.penpot_url}/api/rpc/command/import-file"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (path.name, path.read_bytes(), "application/zip")}
                data = {}
                if project_id:
                    data["project-id"] = project_id
                if file_name:
                    data["name"] = file_name

                resp = await client.post(url, headers={"Authorization": f"Token {self.token}"}, data=data, files=files)
                if resp.status_code in (200, 201):
                    result = resp.json()
                    log.info("[penpot_sync] Successfully imported file into Penpot instance: %s", result)
                    return {"status": "imported", "penpot_file_id": result.get("id"), "result": result}
                else:
                    log.warning("[penpot_sync] Penpot API import returned %d: %s", resp.status_code, resp.text)
                    return {"status": "local_fallback", "penpot_file_path": str(path), "api_response": resp.text}

        except Exception as e:
            log.error("[penpot_sync] Error during Penpot API upload: %s", e)
            return {"status": "local_fallback", "penpot_file_path": str(path), "error": str(e)}
