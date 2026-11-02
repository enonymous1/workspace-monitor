"""Google Voice overview: manual log only, no live sync.

Google Voice has no public API (personal or Workspace), and
automated access violates its Acceptable Use Policy, so this
page deliberately does not pull calls, texts, or voicemails.
It is a manual overview: the business number, hours, and
greeting are recorded here as text, staff log calls and
voicemails by hand, and the page links out to Voice itself
for the real inbox. Any future live phone sync would need a
different provider with a real API (for example a VoIP
provider), not Google Voice.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required

bp = Blueprint("voice", __name__)

DIRECTIONS = ["inbound", "outbound", "voicemail", "missed"]


@bp.route("/voice")
@login_required
def voice():
    user = get_current_user()
    conn = get_db_connection()
    try:
        logs = conn.execute("SELECT * FROM voice_logs ORDER BY date DESC LIMIT 200").fetchall()
        follow_ups = conn.execute(
            "SELECT COUNT(*) FROM voice_logs WHERE follow_up_needed = 1"
        ).fetchone()[0]
    finally:
        conn.close()
    return render_template(
        "voice.html",
        user=user,
        logs=[dict(row) for row in logs],
        follow_ups=follow_ups,
        directions=DIRECTIONS,
        can_manage=is_privileged(user["role"]),
    )


@bp.route("/voice/log", methods=["POST"])
@login_required
def add_log():
    user = get_current_user()
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")
    direction = request.form.get("direction", "inbound")
    date = request.form.get("date", "").strip()
    if direction not in DIRECTIONS or not date:
        flash("A date and a valid direction are required.", "error")
        return redirect(url_for("voice.voice"))
    try:
        duration = (
            float(request.form.get("duration_minutes", ""))
            if request.form.get("duration_minutes", "").strip()
            else None
        )
    except ValueError:
        duration = None
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO voice_logs (date, direction, contact, duration_minutes, outcome, follow_up_needed, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                date,
                direction,
                request.form.get("contact", "").strip(),
                duration,
                request.form.get("outcome", "").strip(),
                1 if request.form.get("follow_up_needed") else 0,
                request.form.get("notes", "").strip(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Voice log entry saved.", "success")
    return redirect(url_for("voice.voice"))


@bp.route("/voice/log/delete/<int:log_id>", methods=["POST"])
@login_required
def delete_log(log_id: int):
    user = get_current_user()
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM voice_logs WHERE id = ?", (log_id,))
        conn.commit()
    finally:
        conn.close()
    flash("Voice log entry deleted.", "success")
    return redirect(url_for("voice.voice"))
