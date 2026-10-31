"""Home dashboard: counts only, no row transfer.

v2's Streamlit home page fetched list endpoints capped at 100
rows and reported their lengths as totals, which went silently
wrong past 100 rows. Counts here come from COUNT(*).
"""

from __future__ import annotations

from flask import Blueprint, render_template

from workspace_monitor.auth import is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    user = get_current_user()
    conn = get_db_connection()
    try:
        if is_privileged(user["role"]):
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            attendance = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM mileage_log WHERE status = 'pending'"
            ).fetchone()[0]
        else:
            users = 1
            attendance = conn.execute(
                "SELECT COUNT(*) FROM attendance WHERE user_email = ?", (user["email"],)
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM mileage_log WHERE user_email = ? AND status = 'pending'",
                (user["email"],),
            ).fetchone()[0]
    finally:
        conn.close()
    return render_template(
        "home.html",
        user=user,
        users=users,
        attendance_records=attendance,
        pending_mileage=pending,
    )
