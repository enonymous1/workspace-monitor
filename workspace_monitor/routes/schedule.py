"""Schedule: server-rendered week view, read-only.

v2's Streamlit calendar used a JavaScript calendar widget; here
the week table is rendered server-side, which is what makes the
static freeze work (the table is in the HTML, not built by a
client-side widget). There is still no create/edit/delete:
events come from the seed data or direct database edits.
Standard users always see only their own events, even if they
pass another user's email in the filter.
"""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, render_template, request

from workspace_monitor.auth import is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required

bp = Blueprint("schedule", __name__)


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


@bp.route("/schedule")
@login_required
def schedule():
    user = get_current_user()
    today = date.today()
    # Week starting Monday of the current week, unless overridden.
    week_start = _parse_date(
        request.args.get("week_start"), today - timedelta(days=today.weekday())
    )
    week_end = week_start + timedelta(days=6)
    selected_users = request.args.getlist("user_emails")
    start_filter = request.args.get("start")
    end_filter = request.args.get("end")

    conditions: list[str] = []
    params: list = []
    if is_privileged(user["role"]):
        if selected_users:
            placeholders = ",".join(["?"] * len(selected_users))
            conditions.append(f"user_email IN ({placeholders})")
            params.extend(selected_users)
    else:
        conditions.append("user_email = ?")
        params.append(user["email"])
    # Week view always constrains to the displayed week; explicit
    # start/end filters narrow it further.
    conditions.append("start_time >= ?")
    params.append(f"{week_start.isoformat()} 00:00:00")
    conditions.append("end_time <= ?")
    params.append(f"{week_end.isoformat()} 23:59:59")
    if start_filter:
        conditions.append("start_time >= ?")
        params.append(f"{start_filter} 00:00:00")
    if end_filter:
        conditions.append("end_time <= ?")
        params.append(f"{end_filter} 23:59:59")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM schedule {where} ORDER BY start_time ASC LIMIT 500", params
        ).fetchall()
        all_users = (
            conn.execute("SELECT email, full_name FROM users ORDER BY full_name").fetchall()
            if is_privileged(user["role"])
            else []
        )
    finally:
        conn.close()

    # Group events by day for the week table.
    days: list[dict] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        day_events = [dict(r) for r in rows if dict(r)["start_time"][:10] == day.isoformat()]
        days.append({"date": day, "events": day_events})
    return render_template(
        "schedule.html",
        user=user,
        days=days,
        week_start=week_start,
        prev_week=week_start - timedelta(days=7),
        next_week=week_start + timedelta(days=7),
        all_users=[dict(u) for u in all_users],
        selected_users=selected_users,
    )
