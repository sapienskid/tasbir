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


class TestInteractiveTier:
    """Interactive editor endpoints use their own bucket (ADR-0023)."""

    @staticmethod
    def _fake_redis(monkeypatch, capacity_seen):
        from app.core import ratelimit

        class Fake:
            def __init__(self):
                self.tokens: dict[str, float] = {}

            async def eval(self, _lua, _n, bucket, capacity, *_rest):
                capacity_seen[bucket] = capacity
                left = self.tokens.get(bucket, capacity)
                if left >= 1:
                    self.tokens[bucket] = left - 1
                    return 1
                return 0

        fake = Fake()

        async def get():
            return fake

        monkeypatch.setattr(ratelimit, "_get_redis", get)
        return fake

    async def test_buckets_are_independent(self, authed_client: AsyncClient, monkeypatch):
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "rate_limit_per_min", 2)
        monkeypatch.setattr(settings, "rate_limit_interactive_per_min", 5)
        seen: dict = {}
        self._fake_redis(monkeypatch, seen)
        h = {"x-api-key": "test-key"}

        # Exhaust the default bucket (2 tokens).
        assert (await authed_client.get("/api/tasks", headers=h)).status_code == 200
        assert (await authed_client.get("/api/tasks", headers=h)).status_code == 200
        assert (await authed_client.get("/api/tasks", headers=h)).status_code == 429

        # The interactive endpoints are unaffected and draw from their own bucket.
        url = "/api/tasks/nope/formats/instagram-square/editor"
        for _ in range(5):
            assert (await authed_client.get(url, headers=h)).status_code == 404
        assert (await authed_client.get(url, headers=h)).status_code == 429
        # ...and exhausting interactive did not refill/steal the default one.
        assert (await authed_client.get("/api/tasks", headers=h)).status_code == 429
        assert seen["rl:token:test-key"] == 2.0
        assert seen["rl:interactive:test-key"] == 5.0

    async def test_compose_previews_are_interactive(self, authed_client: AsyncClient, monkeypatch):
        seen: dict = {}
        self._fake_redis(monkeypatch, seen)
        h = {"x-api-key": "test-key"}
        await authed_client.get("/api/compose/illustration", headers=h)
        assert "rl:interactive:test-key" in seen and "rl:token:test-key" not in seen

    async def test_interactive_fails_open(self, authed_client: AsyncClient, monkeypatch):
        from app.core import ratelimit

        async def boom():
            raise RuntimeError("redis down")

        monkeypatch.setattr(ratelimit, "_get_redis", boom)
        res = await authed_client.get(
            "/api/tasks/nope/formats/instagram-square/editor", headers={"x-api-key": "test-key"}
        )
        assert res.status_code == 404  # reached the handler, not 429/500
