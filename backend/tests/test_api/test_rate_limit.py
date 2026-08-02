"""Rate limiting tests — Redis is mocked; the token bucket must reject at 0 tokens."""

from httpx import AsyncClient


class TestRateLimit:
    async def test_allows_when_tokens_available(self, authed_client: AsyncClient, monkeypatch):
        from unittest.mock import AsyncMock

        from app.core import ratelimit

        fake_redis = AsyncMock()
        fake_redis.eval = AsyncMock(return_value=1)
        monkeypatch.setattr(ratelimit, "_get_redis", AsyncMock(return_value=fake_redis))

        res = await authed_client.get("/api/tasks", headers={"x-api-key": "test-key"})
        assert res.status_code == 200

    async def test_429_when_bucket_exhausted(self, authed_client: AsyncClient, monkeypatch):
        from unittest.mock import AsyncMock

        from app.core import ratelimit

        fake_redis = AsyncMock()
        fake_redis.eval = AsyncMock(return_value=0)
        monkeypatch.setattr(ratelimit, "_get_redis", AsyncMock(return_value=fake_redis))

        res = await authed_client.get("/api/tasks", headers={"x-api-key": "test-key"})
        assert res.status_code == 429

    async def test_fails_open_when_redis_unavailable(self, authed_client: AsyncClient, monkeypatch):

        from app.core import ratelimit

        async def boom():
            raise RuntimeError("redis down")

        monkeypatch.setattr(ratelimit, "_get_redis", boom)

        res = await authed_client.get("/api/tasks", headers={"x-api-key": "test-key"})
        assert res.status_code == 200
