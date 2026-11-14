from utils.ratelimit import RateLimiter


def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(limit=3, window_seconds=60)
    assert [limiter.hit("a", now=t)[0] for t in (0, 1, 2)] == [True, True, True]
    allowed, retry_after = limiter.hit("a", now=3)
    assert allowed is False
    assert 1 <= retry_after <= 60


def test_window_slides_and_keys_are_independent():
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.hit("a", now=0)[0] is True
    assert limiter.hit("a", now=5)[0] is False
    assert limiter.hit("b", now=5)[0] is True
    assert limiter.hit("a", now=10)[0] is True


def test_zero_limit_disables_limiting():
    limiter = RateLimiter(limit=0, window_seconds=60)
    assert all(limiter.hit("a", now=i)[0] for i in range(100))
