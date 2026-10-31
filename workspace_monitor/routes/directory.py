"""Directory: searchable contacts with universal vs assigned visibility.

Admins may create contacts for anyone and delete any contact;
other users may only create contacts for themselves and delete
their own. Supervisors see all contacts but cannot manage
others' — the same matrix as the v2 API.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import Role, is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required, pagination_args

bp = Blueprint("directory", __name__)


@bp.route("/directory")
@login_required
def directory():
    user = get_current_user()
    limit, offset = pagination_args()
    search = (request.args.get("q") or "").strip()
    conn = get_db_connection()
    try:
        if is_privileged(user["role"]):
            base = "SELECT * FROM contacts"
            params: list = []
        else:
            base = "SELECT * FROM contacts WHERE owner_email = 'universal' OR owner_email = ?"
            params = [user["email"]]
        if search:
            like = f"%{search}%"
            base += " AND " if "WHERE" in base else " WHERE "
            base += "(full_name LIKE ? OR job_title LIKE ? OR email LIKE ?)"
            params.extend([like, like, like])
        rows = conn.execute(
            f"{base} ORDER BY full_name ASC LIMIT ? OFFSET ?", (*params, limit, offset)
        ).fetchall()
    finally:
        conn.close()
    return render_template("directory.html", user=user, rows=[dict(r) for r in rows], search=search)


@bp.route("/directory/add", methods=["POST"])
@login_required
def add_contact():
    user = get_current_user()
    owner_email = request.form.get("owner_email", user["email"]).strip() or user["email"]
    if user["role"] != Role.ADMIN and owner_email != user["email"]:
        flash("Not authorized to create contacts for other users.", "error")
        return redirect(url_for("directory.directory"))
    email = request.form.get("email", "").strip()
    if "@" not in email:
        flash("A valid email address is required.", "error")
        return redirect(url_for("directory.directory"))
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO contacts (owner_email, full_name, job_title, email, phone, category)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                owner_email,
                request.form.get("full_name", "").strip(),
                request.form.get("job_title", "").strip(),
                email,
                request.form.get("phone", "").strip(),
                request.form.get("category", "").strip(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Contact saved.", "success")
    return redirect(url_for("directory.directory"))


@bp.route("/directory/delete/<int:contact_id>", methods=["POST"])
@login_required
def delete_contact(contact_id: int):
    user = get_current_user()
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT owner_email FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not row:
            flash("Contact not found.", "error")
            return redirect(url_for("directory.directory"))
        if user["role"] != Role.ADMIN and row["owner_email"] != user["email"]:
            flash("Not authorized to delete this contact.", "error")
            return redirect(url_for("directory.directory"))
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
    finally:
        conn.close()
    flash("Contact deleted.", "success")
    return redirect(url_for("directory.directory"))
