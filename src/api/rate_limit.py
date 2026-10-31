"""Failed-login rate limiting (in-process, per client IP).

This is a local defence, not a production rate limiter: it lives
in memory, so it resets on restart and does not span workers.
Production deployments must also rate-limit ``POST /api/login``
at the reverse proxy (see README Deployment). The in-process
limiter still stops the trivial case — a single client hammering
login — and it is fully testable without a proxy.

Policy: after ``max_failures`` failed logins from one IP within
``window``, further login attempts from that IP get 429 until
the window passes. Successful logins clear the IP's failure
history. Limits are configurable via environment so tests can
raise them without touching the default:

- ``WORKSPACE_MONITOR_LOGIN_MAX_FAILURES`` (default 5)
- ``WORKSPACE_MONITOR_LOGIN_WINDOW_SECONDS`` (default 900)
"""

from __future__ import annotations

import os
import threading
import time


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class LoginRateLimiter:
    """Thread-safe sliding-window counter of failed logins per IP."""

    def __init__(self, max_failures: int | None = None, window_seconds: int | None = None):
        self.max_failures = (
            max_failures
            if max_failures is not None
            else _int_env("WORKSPACE_MONITOR_LOGIN_MAX_FAILURES", 5)
        )
        self.window_seconds = (
            window_seconds
            if window_seconds is not None
            else _int_env("WORKSPACE_MONITOR_LOGIN_WINDOW_SECONDS", 900)
        )
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, ip: str, now: float) -> list[float]:
        failures = [t for t in self._failures.get(ip, []) if now - t < self.window_seconds]
        if failures:
            self._failures[ip] = failures
        else:
            self._failures.pop(ip, None)
        return failures

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            return len(self._prune(ip, time.time())) >= self.max_failures

    def record_failure(self, ip: str) -> None:
        with self._lock:
            now = time.time()
            failures = self._prune(ip, now)
            failures.append(now)
            self._failures[ip] = failures

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)


# Process-wide limiter used by the login endpoint.
login_limiter = LoginRateLimiter()
