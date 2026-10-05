"""Per-key token-bucket rate limiting backed by Redis.

A single Redis hash per bucket holds the remaining tokens and the last
refill timestamp. A Lua script does the check-and-decrement atomically so
concurrent requests from the same key cannot overspend a token.

Two tiers (ADR-0023): ``default`` (generation, CRUD, everything else) and
``interactive`` (the Studio editor's preview / refill / editor-state traffic
and the composer's previews + thumbnails). They use **separate buckets** so a
burst of editing never starves generation calls and vice versa. An endpoint
opts into the interactive tier with the :func:`interactive` decorator; the
router-level :func:`rate_limiter` dependency reads the marker, so a request
is only ever counted against one bucket.

Fails open (allows the request) only when Redis itself is unreachable —
the request would fail anyway once the pipeline tries to enqueue.
"""

from __future__ import annotations

import logging
import time

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.core.security import api_key_header

log = logging.getLogger(__name__)

# tokens refill per second; default 30/min = 0.5/s
_REFILL_PER_SECOND = 0.5
_BUCKET_TTL = 120

_TIER_ATTR = "__rate_tier__"
TIER_DEFAULT = "default"
TIER_INTERACTIVE = "interactive"

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


def interactive(fn):
    """Mark a route handler as interactive-tier (own bucket, higher limit).

    Apply *under* the router decorator so the marker lands on the function
    the route registers::

        @router.post("/preview")
        @interactive
        async def preview(...): ...
    """
    setattr(fn, _TIER_ATTR, TIER_INTERACTIVE)
    return fn


def request_tier(request: Request) -> str:
    """The rate-limit tier of the endpoint serving ``request``."""
    endpoint = request.scope.get("endpoint")
    return getattr(endpoint, _TIER_ATTR, TIER_DEFAULT)


def _tier_config(tier: str, settings: Settings) -> tuple[str, int]:
    """(bucket key prefix, requests/minute) for a tier."""
    if tier == TIER_INTERACTIVE:
        return "rl:interactive", settings.rate_limit_interactive_per_min
    return "rl:token", settings.rate_limit_per_min


async def consume(tier: str, api_key: str | None, settings: Settings) -> None:
    """Take one token from the caller's bucket for ``tier`` (429 when empty)."""
    prefix, per_min = _tier_config(tier, settings)
    if per_min <= 0:
        return

    bucket = f"{prefix}:{api_key or 'anonymous'}"
    capacity = float(per_min)
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


async def rate_limiter(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Token-bucket rate limit keyed by API key (anonymous bucket otherwise).

    The bucket (and its capacity) depends on the endpoint's tier — see
    :func:`interactive`.
    """
    await consume(request_tier(request), api_key, settings)


async def interactive_rate_limiter(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Force the interactive bucket for every route on the router.

    Used by the settings/config routers: browsing the Studio (Settings,
    Agents, Design Systems) is not generation traffic and must not compete
    with ``POST /generate`` for the small default bucket.
    """
    await consume(TIER_INTERACTIVE, api_key, settings)
