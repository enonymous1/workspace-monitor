"""workspace-monitor, Flask build (v3).

Flask + Jinja2, app factory, SQLite. This replaces the v2
FastAPI + Streamlit build: one process instead of two,
server-rendered templates instead of Streamlit page scripts,
and server-side sessions instead of JWTs. The database schema,
demo seed, role rules, and feature set are carried over
unchanged — only the web layer changed.

Run it with ``python run_app.py`` (or ``flask --app
workspace_monitor run`` after installing). The database is
created on first start; seed the demo dataset with
``python scripts/seed_demo.py`` (auto-seed is opt-in via
``WORKSPACE_MONITOR_AUTO_SEED=1`` and must never be enabled
in production).
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from flask import Flask, session

from workspace_monitor.config import Settings
from workspace_monitor.rate_limit import LoginRateLimiter

__version__ = "3.2.0"

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> Flask:
    """Build the Flask app. ``settings`` overrides the environment
    (tests pass a throwaway database and a fixed secret here)."""
    settings = settings or Settings.from_env()
    secret_key = settings.secret_key
    if not secret_key:
        logger.warning(
            "WORKSPACE_MONITOR_SECRET_KEY is not set; using an ephemeral "
            "per-process secret. Set the variable for stable logins."
        )
        secret_key = secrets.token_hex(32)

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=secret_key,
        WM_DB_PATH=settings.db_path,
        WM_TIMEOUT=settings.api_timeout_seconds,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    app.extensions["login_limiter"] = LoginRateLimiter(
        max_failures=settings.login_max_failures,
        window_seconds=settings.login_window_seconds,
    )

    from workspace_monitor.database import init_db, seed_demo_data
    from workspace_monitor.helpers import check_csrf, csrf_token, get_current_user

    init_db(settings.db_path)
    if settings.auto_seed:
        seed_demo_data(settings.db_path)

    @app.before_request
    def _before_request():
        check_csrf()

    @app.context_processor
    def _inject_helpers():
        return {"current_user": get_current_user(), "csrf_token": csrf_token()}

    from workspace_monitor.routes import (
        attendance,
        auth,
        classroom,
        collateral,
        directory,
        distance,
        hr,
        main,
        mileage,
        schedule,
        users,
        voice,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(attendance.bp)
    app.register_blueprint(schedule.bp)
    app.register_blueprint(mileage.bp)
    app.register_blueprint(directory.bp)
    app.register_blueprint(distance.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(collateral.bp)
    app.register_blueprint(hr.bp)
    app.register_blueprint(voice.bp)
    app.register_blueprint(classroom.bp)

    # Session housekeeping: drop a stale user marker if the
    # account no longer resolves (suspended/deleted).
    @app.after_request
    def _after_request(response):
        if session.get("user_email") and get_current_user() is None:
            session.clear()
        return response

    return app
