"""Per-key token-bucket rate limiting backed by Redis.

A single Redis hash per bucket holds the remaining tokens and the last
refill timestamp. A Lua script does the check-and-decrement atomically so
concurrent requests from the same key cannot overspend a token.

Fails open (allows the request) only when Redis itself is unreachable —
the request would fail anyway once the pipeline tries to enqueue.
"""

from __future__ import annotations

import logging
import time

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.core.security import api_key_header

log = logging.getLogger(__name__)

# tokens refill per second; default 30/min = 0.5/s
_REFILL_PER_SECOND = 0.5
_BUCKET_TTL = 120

_TOKEN_BUCKET_LUA = """
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens') or ARGV[1])
local ts = tonumber(redis.call('HGET', KEYS[1], 'ts') or ARGV[3])
local elapsed = math.max(0, ARGV[3] - ts)
local rate = tonumber(ARGV[2])
tokens = math.min(tonumber(ARGV[1]), tokens + elapsed * rate)
if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', ARGV[3])
    redis.call('EXPIRE', KEYS[1], ARGV[4])
    return 1
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 0
"""

_redis: Redis | None = None


async def _get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def rate_limiter(
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Token-bucket rate limit keyed by API key (anonymous bucket otherwise)."""
    if settings.rate_limit_per_min <= 0:
        return

    bucket_key = api_key or "anonymous"
    bucket = f"rl:token:{bucket_key}"
    capacity = float(settings.rate_limit_per_min)
    now = int(time.time())

    try:
        redis = await _get_redis()
        allowed = await redis.eval(
            _TOKEN_BUCKET_LUA,
            1,
            bucket,
            capacity,
            capacity / 60.0,
            now,
            _BUCKET_TTL,
        )
    except Exception as e:  # Redis unavailable — fail open
        log.warning("[ratelimit] Redis unavailable, allowing request: %s", e)
        return

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded — retry shortly",
        )
