"""Shared request helpers: current user, visibility, CSRF, pagination.

Every request re-checks the session's user against the database,
so a suspension or role change takes effect without waiting for
a session to expire — the same rule the v2 JWT build enforced
by re-reading the user on every request.
"""

from __future__ import annotations

import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from workspace_monitor.auth import Role, is_privileged
from workspace_monitor.database import get_db_connection


def get_current_user() -> dict | None:
    """Resolve the session to a user row, or None if not logged in.

    The cache is keyed by the session email, not just by
    "already looked up": login sets the session email mid-request
    (after an initial anonymous lookup), and the after-request
    hook must see the new user, not the cached anonymous None.
    That stale-cache bug cleared the session on every login.
    """
    email = session.get("user_email")
    if g.get("_current_user_loaded") and g.get("_current_user_email") == email:
        return g.get("_current_user")
    g._current_user_loaded = True
    g._current_user_email = email
    if not email:
        g._current_user = None
        return None
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT email, full_name, department, title, role, is_suspended FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or row["is_suspended"]:
        session.clear()
        g._current_user = None
        return None
    user = dict(row)
    user["role"] = Role.normalize(user["role"])
    g._current_user = user
    return user


def login_required(view):
    """Redirect to login when there is no current user."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def visible_email(user: dict, requested: str | None) -> str | None:
    """Email filter for a list view: privileged users may filter,
    Standard users always see only their own rows."""
    if is_privileged(user["role"]):
        return requested or None
    return user["email"]


def csrf_token() -> str:
    """Per-session CSRF token, created lazily."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def check_csrf() -> None:
    """Validate the CSRF token on POST; 400 on mismatch.

    Skipped in testing so the test client can post without
    first parsing a form — CSRF itself is covered by a
    dedicated test with testing disabled.
    """
    from flask import current_app

    if request.method != "POST" or current_app.config.get("TESTING"):
        return
    session_token = session.get("csrf_token", "")
    form_token = request.form.get("csrf_token", "")
    # An empty session token must not match an empty form token:
    # a first POST with no prior GET would otherwise pass.
    if not session_token or not secrets.compare_digest(form_token, session_token):
        abort(400, "Invalid CSRF token")


def pagination_args(default_limit: int = 100) -> tuple[int, int]:
    """Shared limit/offset parsing: limit clamped to 1..500."""
    try:
        limit = int(request.args.get("limit", default_limit))
    except ValueError:
        limit = default_limit
    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0
    return max(1, min(limit, 500)), max(0, offset)
