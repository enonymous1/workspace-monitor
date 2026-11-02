"""User management: Admin only.

Internal users are login accounts in the ``users`` table.
External people are *not* here — they live in Directory
(contacts), with no login. That split is deliberate: giving
an external contact a row here would create a login account.

There is no delete: suspend instead, so attendance, mileage,
and schedule history tied to the email stays intact. Admins
cannot suspend themselves, and the last Admin cannot be
demoted — both would lock the workspace out of admin.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import Role, hash_password
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import admin_required, get_current_user, login_required

bp = Blueprint("users", __name__)


@bp.route("/users")
@login_required
@admin_required
def users():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT email, full_name, department, title, role, is_suspended, last_login_time"
            " FROM users ORDER BY full_name ASC"
        ).fetchall()
    finally:
        conn.close()
    return render_template("users.html", user=get_current_user(), rows=[dict(r) for r in rows])


@bp.route("/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    email = request.form.get("email", "").strip()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")
    role = Role.normalize(request.form.get("role", "Standard"))
    if "@" not in email or not full_name:
        flash("A valid email and a full name are required.", "error")
        return redirect(url_for("users.users"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("users.users"))
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("A user with that email already exists.", "error")
            return redirect(url_for("users.users"))
        conn.execute(
            "INSERT INTO users (email, full_name, department, title, is_suspended, role, password_hash)"
            " VALUES (?, ?, ?, ?, 0, ?, ?)",
            (
                email,
                full_name,
                request.form.get("department", "").strip(),
                request.form.get("title", "").strip(),
                role.value,
                hash_password(password),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash(f"User {email} created.", "success")
    return redirect(url_for("users.users"))


@bp.route("/users/update", methods=["POST"])
@login_required
@admin_required
def update_user():
    current = get_current_user()
    email = request.form.get("email", "").strip()
    new_role = Role.normalize(request.form.get("role", "Standard"))
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT role FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            flash("User not found.", "error")
            return redirect(url_for("users.users"))
        if Role.normalize(row["role"]) == Role.ADMIN and new_role != Role.ADMIN:
            admin_count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'Admin' AND is_suspended = 0"
            ).fetchone()[0]
            if admin_count <= 1:
                flash("Cannot demote the last active Admin.", "error")
                return redirect(url_for("users.users"))
        conn.execute(
            "UPDATE users SET full_name = ?, department = ?, title = ?, role = ? WHERE email = ?",
            (
                request.form.get("full_name", "").strip(),
                request.form.get("department", "").strip(),
                request.form.get("title", "").strip(),
                new_role.value,
                email,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    if email == current["email"]:
        # Role change for self takes effect on the next request
        # (get_current_user re-reads the database every time).
        pass
    flash(f"User {email} updated.", "success")
    return redirect(url_for("users.users"))


@bp.route("/users/suspend", methods=["POST"])
@login_required
@admin_required
def suspend_user():
    current = get_current_user()
    email = request.form.get("email", "").strip()
    if email == current["email"]:
        flash("You cannot suspend your own account.", "error")
        return redirect(url_for("users.users"))
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET is_suspended = 1 WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
    flash(f"User {email} suspended.", "success")
    return redirect(url_for("users.users"))


@bp.route("/users/reactivate", methods=["POST"])
@login_required
@admin_required
def reactivate_user():
    email = request.form.get("email", "").strip()
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET is_suspended = 0 WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
    flash(f"User {email} reactivated.", "success")
    return redirect(url_for("users.users"))


@bp.route("/users/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_password():
    email = request.form.get("email", "").strip()
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if len(new_password) < 8 or new_password != confirm:
        flash("New password must be at least 8 characters and match its confirmation.", "error")
        return redirect(url_for("users.users"))
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            flash("User not found.", "error")
            return redirect(url_for("users.users"))
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (hash_password(new_password), email),
        )
        conn.commit()
    finally:
        conn.close()
    # Admin-initiated reset only. There is no self-service reset
    # yet (no email sending in this app); the admin must pass
    # the new password to the user through a separate channel.
    flash(
        f"Password reset for {email}. Share the new password securely, outside this app.", "success"
    )
    return redirect(url_for("users.users"))
