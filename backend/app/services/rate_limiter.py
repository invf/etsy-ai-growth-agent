"""Redis-backed token bucket, shared across workers/processes.

Etsy allows ~10 req/s per application, so the bucket key is global,
not per store.
"""
import time

import redis

from app.core.config import settings

TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local last = tonumber(redis.call('hget', key, 'last') or now)
local tokens = tonumber(redis.call('hget', key, 'tokens') or capacity)

local delta = math.max(0, now - last)
tokens = math.min(capacity, tokens + delta * rate)

if tokens >= 1 then
    redis.call('hset', key, 'tokens', tokens - 1, 'last', now)
    redis.call('expire', key, 60)
    return 1
end
redis.call('hset', key, 'tokens', tokens, 'last', now)
redis.call('expire', key, 60)
return 0
"""


class RateLimitTimeout(Exception):
    pass


class TokenBucketRateLimiter:
    def __init__(
        self,
        redis_client: redis.Redis,
        rate: float = 10,
        capacity: float = 10,
        key: str = "ratelimit:etsy:global",
    ):
        self.redis = redis_client
        self.rate = rate
        self.capacity = capacity
        self.key = key

    def acquire(self, timeout: float = 30.0) -> None:
        """Block until a token is available; raise RateLimitTimeout after `timeout`."""
        deadline = time.monotonic() + timeout
        while True:
            granted = self.redis.eval(
                TOKEN_BUCKET_LUA,
                1,
                self.key,
                str(self.capacity),
                str(self.rate),
                str(time.time()),
            )
            if granted == 1:
                return
            if time.monotonic() >= deadline:
                raise RateLimitTimeout(f"No token within {timeout}s for {self.key}")
            time.sleep(0.1)


_etsy_limiter: TokenBucketRateLimiter | None = None


def get_etsy_rate_limiter() -> TokenBucketRateLimiter:
    global _etsy_limiter
    if _etsy_limiter is None:
        qps = settings.ETSY_RATE_LIMIT_QPS
        _etsy_limiter = TokenBucketRateLimiter(
            redis.from_url(settings.REDIS_URL), rate=qps, capacity=qps
        )
    return _etsy_limiter
