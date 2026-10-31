"""Failed-login rate limiting (in-process, per client IP).

Same policy as the v2 API limiter: after ``max_failures``
failed logins from one IP within ``window``, further login
attempts get a 429 until the window passes. Successful logins
clear the IP's history. This is a local defence, not a
production rate limiter: it resets on restart and does not
span workers. Production deployments must also rate-limit
``POST /login`` at the reverse proxy (see README Deployment).
"""

from __future__ import annotations

import threading
import time


class LoginRateLimiter:
    """Thread-safe sliding-window counter of failed logins per IP."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 900):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
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
