"""Tests for Brands API endpoints (CRUD, brand update, logo upload)."""

import pytest
from httpx import AsyncClient
from app.core.dependencies import get_db
from app.main import app


@pytest.mark.asyncio
async def test_brands_get_list(async_client: AsyncClient, db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        res = await async_client.get("/brands")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
    finally:
        app.dependency_overrides.clear()
