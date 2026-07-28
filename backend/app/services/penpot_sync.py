"""Penpot API Sync Service — Automatically imports generated .penpot files into Penpot.

Uses the authenticated RPC API (import-binfile) to push files directly into
the user's Penpot workspace without any manual steps.
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
        self.penpot_url = (penpot_url or getattr(settings, "penpot_url", "http://penpot-backend:6060")).rstrip("/")
        self.token = access_token or getattr(settings, "penpot_access_token", "")

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.token}"} if self.token else {}

    async def _get_default_project_id(self, client: httpx.AsyncClient) -> str | None:
        """Fetch the user's default project ID from their profile."""
        try:
            resp = await client.post(
                f"{self.penpot_url}/api/rpc/command/get-profile",
                headers=self._auth_headers,
            )
            if resp.status_code == 200:
                data = resp.text
                # Parse the Transit+JSON encoded response to extract default-team-id
                # The response looks like: ["^ ", "~:default-team-id", "~uXXX-...", ...]
                import re
                team_match = re.search(r'"~:default-team-id","~u([0-9a-f-]+)"', data)
                project_match = re.search(r'"~:default-project-id","~u([0-9a-f-]+)"', data)

                if project_match:
                    project_id = project_match.group(1)
                    log.info("[penpot_sync] Found default project-id: %s", project_id)
                    return project_id
        except Exception as e:
            log.warning("[penpot_sync] Could not fetch profile: %s", e)
        return None

    async def auto_import_penpot_file(
        self,
        penpot_file_path: str | Path,
        project_id: str | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """Automatically upload a .penpot file into Penpot via the import-binfile API."""
        path = Path(penpot_file_path)
        if not path.exists():
            raise FileNotFoundError(f".penpot file not found: {path}")

        if not self.token:
            log.info(
                "[penpot_sync] No Penpot token configured — file saved locally at %s", path
            )
            return {"status": "ready_local", "penpot_file_path": str(path)}

        url = f"{self.penpot_url}/api/rpc/command/import-binfile"
        import_name = file_name or path.stem

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Auto-discover project ID if not provided
                if not project_id:
                    project_id = await self._get_default_project_id(client)

                if not project_id:
                    log.warning("[penpot_sync] No project-id available, saving locally")
                    return {"status": "ready_local", "penpot_file_path": str(path)}

                file_bytes = path.read_bytes()
                files = {"file": (path.name, file_bytes, "application/zip")}
                data = {
                    "project-id": project_id,
                    "name": import_name,
                }

                log.info("[penpot_sync] Importing '%s' into project %s ...", import_name, project_id)
                async with client.stream("POST", url, headers=self._auth_headers, data=data, files=files) as resp:
                    if resp.status_code != 200:
                        log.warning("[penpot_sync] import-binfile returned %d", resp.status_code)
                        return {"status": "import_failed", "penpot_file_path": str(path), "http_status": resp.status_code}

                    error_found = False
                    async for line in resp.aiter_lines():
                        if "event: error" in line or ('"~:type","~:error"' in line):
                            error_found = True
                            log.warning("[penpot_sync] Penpot backend error: %s", line)
                    
                    if error_found:
                        return {"status": "import_failed", "penpot_file_path": str(path)}

                    log.info("[penpot_sync] Successfully imported '%s' into Penpot", import_name)
                    return {
                        "status": "imported",
                        "project_id": project_id,
                        "file_name": import_name,
                        "penpot_file_path": str(path),
                    }

        except Exception as e:
            log.error("[penpot_sync] Error during Penpot API import: %s", e)
            return {"status": "error", "penpot_file_path": str(path), "error": str(e)}
