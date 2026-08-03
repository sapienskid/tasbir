"""Tests for the health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "tasbir"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_response_structure(async_client: AsyncClient):
    response = await async_client.get("/health")
    data = response.json()
    assert isinstance(data["version"], str)
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_reports_checks(async_client: AsyncClient):
    """Readiness returns 200/503 but always reports per-dependency checks."""
    response = await async_client.get("/health/ready")
    assert response.status_code in (200, 503)
    data = response.json()
    assert set(data["checks"]) == {"sqlite", "redis", "render"}
    assert data["status"] in ("ready", "not_ready")
    for name, check in data["checks"].items():
        assert check["ok"] in (True, False)
