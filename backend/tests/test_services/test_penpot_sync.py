"""Tests for Penpot API Sync Service."""

from pathlib import Path
import pytest
from app.services.penpot_sync import PenpotAPISync


@pytest.mark.asyncio
async def test_penpot_sync_local_fallback_when_no_token(tmp_path: Path):
    dummy_file = tmp_path / "test.penpot"
    dummy_file.write_bytes(b"PK\x03\x04...")

    client = PenpotAPISync(penpot_url="http://localhost:9001", access_token="")
    res = await client.auto_import_penpot_file(dummy_file)
    assert res["status"] == "ready_local"
    assert res["penpot_file_path"] == str(dummy_file)


@pytest.mark.asyncio
async def test_penpot_sync_headers():
    client = PenpotAPISync(access_token="test_token_123")
    headers = client.headers
    assert headers["Authorization"] == "Token test_token_123"
    assert headers["Accept"] == "application/json"
