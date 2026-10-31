"""Login, logout, and failed-login rate limiting.

Sessions are server-side Flask sessions: the cookie holds only
the email, and every request re-checks the user in the database
(see helpers.get_current_user), so suspension and role changes
take effect immediately and logout is simply clearing the
session — no token revocation table, unlike the v2 JWT build.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from workspace_monitor.auth import Role, verify_password
from workspace_monitor.database import get_db_connection

bp = Blueprint("auth", __name__)


def _client_ip() -> str:
    return request.remote_addr or "unknown"


@bp.route("/login", methods=["GET", "POST"])
def login():
    from workspace_monitor.helpers import get_current_user

    if get_current_user() is not None:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        limiter = current_app.extensions["login_limiter"]
        ip = _client_ip()
        if limiter.is_blocked(ip):
            flash("Too many failed login attempts. Try again later.", "error")
            return render_template("login.html"), 429
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT full_name, role, password_hash, is_suspended FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if (
                user is None
                or user["is_suspended"]
                or not verify_password(password, user["password_hash"])
            ):
                # Same response for unknown user / bad password:
                # no user enumeration.
                limiter.record_failure(ip)
                flash("Invalid email or password.", "error")
                return render_template("login.html"), 401
            conn.execute(
                "UPDATE users SET last_login_time = ? WHERE email = ?",
                (datetime.now(timezone.utc).isoformat(), email),
            )
            conn.commit()
        finally:
            conn.close()
        limiter.record_success(ip)
        session.clear()
        session.permanent = True
        session["user_email"] = email
        session["full_name"] = user["full_name"]
        session["role"] = Role.normalize(user["role"]).value
        return redirect(request.args.get("next") or url_for("main.home"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
