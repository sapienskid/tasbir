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
