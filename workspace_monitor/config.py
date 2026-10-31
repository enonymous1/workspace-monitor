"""Configuration: one place, read from the environment.

This replaces the v2 pattern where ``os.environ`` was read in
several modules at import time. ``create_app`` builds a
``Settings`` and stores it on ``app.config``; routes read it
from there, so tests can construct an app with a throwaway
database and a fixed secret without import ordering tricks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    secret_key: str
    db_path: Path
    auto_seed: bool
    login_max_failures: int
    login_window_seconds: int
    api_timeout_seconds: float
    port: int

    @classmethod
    def from_env(cls, secret_key: str | None = None) -> "Settings":
        return cls(
            secret_key=secret_key or os.environ.get("WORKSPACE_MONITOR_SECRET_KEY", ""),
            db_path=Path(
                os.environ.get(
                    "WORKSPACE_MONITOR_DB",
                    Path(__file__).resolve().parent / "monitor.db",
                )
            ),
            auto_seed=os.environ.get("WORKSPACE_MONITOR_AUTO_SEED", "0") == "1",
            login_max_failures=_int_env("WORKSPACE_MONITOR_LOGIN_MAX_FAILURES", 5),
            login_window_seconds=_int_env("WORKSPACE_MONITOR_LOGIN_WINDOW_SECONDS", 900),
            api_timeout_seconds=float(os.environ.get("WORKSPACE_MONITOR_API_TIMEOUT", "10")),
            port=_int_env("WORKSPACE_MONITOR_PORT", 5000),
        )
