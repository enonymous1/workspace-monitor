"""Login rate limiting: unit tests plus one API-level check.

The API check temporarily lowers the process-wide limiter and
restores it in a finally block, and clears the TestClient IP's
history afterwards, so no other test file is affected.
"""

import time

from api.rate_limit import LoginRateLimiter, login_limiter


def test_limiter_blocks_after_max_failures():
    limiter = LoginRateLimiter(max_failures=3, window_seconds=60)
    assert limiter.is_blocked("1.2.3.4") is False
    limiter.record_failure("1.2.3.4")
    limiter.record_failure("1.2.3.4")
    assert limiter.is_blocked("1.2.3.4") is False
    limiter.record_failure("1.2.3.4")
    assert limiter.is_blocked("1.2.3.4") is True
    limiter.record_success("1.2.3.4")
    assert limiter.is_blocked("1.2.3.4") is False


def test_limiter_window_expires():
    limiter = LoginRateLimiter(max_failures=1, window_seconds=0.05)
    limiter.record_failure("5.6.7.8")
    assert limiter.is_blocked("5.6.7.8") is True
    time.sleep(0.1)
    assert limiter.is_blocked("5.6.7.8") is False


def test_api_login_returns_429_when_blocked(client):
    original_max = login_limiter.max_failures
    login_limiter.max_failures = 2
    try:
        for _ in range(2):
            assert (
                client.post(
                    "/api/login", json={"email": "admin@example.com", "password": "wrong"}
                ).status_code
                == 401
            )
        response = client.post(
            "/api/login", json={"email": "admin@example.com", "password": "wrong"}
        )
        assert response.status_code == 429
    finally:
        login_limiter.max_failures = original_max
        login_limiter.record_success("testclient")
