import pytest

from app.services.rate_limiter import RateLimitTimeout, TokenBucketRateLimiter


class StubRedis:
    """Returns scripted eval results in order, then repeats the last one."""

    def __init__(self, results: list[int]):
        self.results = list(results)
        self.calls = 0

    def eval(self, *args, **kwargs):
        self.calls += 1
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


def test_acquire_returns_immediately_when_token_granted():
    redis = StubRedis([1])
    TokenBucketRateLimiter(redis).acquire(timeout=1)
    assert redis.calls == 1


def test_acquire_retries_until_token_granted():
    redis = StubRedis([0, 0, 1])
    TokenBucketRateLimiter(redis).acquire(timeout=5)
    assert redis.calls == 3


def test_acquire_raises_after_timeout():
    redis = StubRedis([0])
    with pytest.raises(RateLimitTimeout):
        TokenBucketRateLimiter(redis).acquire(timeout=0.3)
    assert redis.calls >= 2
