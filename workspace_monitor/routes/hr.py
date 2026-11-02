"""HR / hiring: roster, job descriptions, and posting channels.

The roster is the internal users table joined to the seeded
``hr_data`` row (pay-cycle hours are Admin-only — Supervisors
see names, departments, and titles, but no pay data, and
Standard users see only their own row).

Job postings are local records only. There is no Indeed sync:
Indeed's posting/application APIs need partner approval and
are not self-serve, so this page stores the description here
and links out to the employer's own Indeed dashboard, where
the actual posting happens. Application counts are entered
manually. No scraping of Indeed is done or offered.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import Role, is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required

bp = Blueprint("hr", __name__)

JOB_STATUSES = ["draft", "open", "closed"]


@bp.route("/hr")
@login_required
def hr():
    user = get_current_user()
    conn = get_db_connection()
    try:
        if user["role"] == Role.ADMIN:
            roster = conn.execute(
                "SELECT u.email, u.full_name, u.department, u.title, u.role, u.is_suspended,"
                " h.current_pay_cycle_hours FROM users u"
                " LEFT JOIN hr_data h ON h.primary_email = u.email ORDER BY u.full_name ASC"
            ).fetchall()
        elif is_privileged(user["role"]):
            roster = conn.execute(
                "SELECT email, full_name, department, title, role, is_suspended, NULL AS current_pay_cycle_hours"
                " FROM users ORDER BY full_name ASC"
            ).fetchall()
        else:
            roster = conn.execute(
                "SELECT email, full_name, department, title, role, is_suspended, NULL AS current_pay_cycle_hours"
                " FROM users WHERE email = ?",
                (user["email"],),
            ).fetchall()
        jobs = conn.execute("SELECT * FROM job_postings ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return render_template(
        "hr.html",
        user=user,
        roster=[dict(r) for r in roster],
        jobs=[dict(j) for j in jobs],
        job_statuses=JOB_STATUSES,
        can_manage=is_privileged(user["role"]),
        show_pay=user["role"] == Role.ADMIN,
    )


@bp.route("/hr/job/add", methods=["POST"])
@login_required
def add_job():
    user = get_current_user()
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")
    title = request.form.get("title", "").strip()
    status = request.form.get("status", "draft")
    if not title or status not in JOB_STATUSES:
        flash("A title and a valid status are required.", "error")
        return redirect(url_for("hr.hr"))
    try:
        applications = int(request.form.get("applications_count", "0"))
    except ValueError:
        applications = 0
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO job_postings (title, description, location, pay_range, status, posting_url, applications_count, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                title,
                request.form.get("description", "").strip(),
                request.form.get("location", "").strip(),
                request.form.get("pay_range", "").strip(),
                status,
                request.form.get("posting_url", "").strip(),
                max(0, applications),
                date.today().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash(f"Job posting {title} saved.", "success")
    return redirect(url_for("hr.hr"))


@bp.route("/hr/job/update/<int:job_id>", methods=["POST"])
@login_required
def update_job(job_id: int):
    user = get_current_user()
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")
    status = request.form.get("status", "draft")
    if status not in JOB_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("hr.hr"))
    try:
        applications = int(request.form.get("applications_count", "0"))
    except ValueError:
        applications = 0
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE job_postings SET status = ?, posting_url = ?, applications_count = ? WHERE id = ?",
            (status, request.form.get("posting_url", "").strip(), max(0, applications), job_id),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Job posting updated.", "success")
    return redirect(url_for("hr.hr"))


@bp.route("/hr/job/delete/<int:job_id>", methods=["POST"])
@login_required
def delete_job(job_id: int):
    user = get_current_user()
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM job_postings WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()
    flash("Job posting deleted.", "success")
    return redirect(url_for("hr.hr"))
