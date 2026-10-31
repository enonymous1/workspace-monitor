"""Attendance: clock in/out and history with a Leaflet map.

Clock-in is atomic: a pre-check gives a friendly error, and
the partial unique index on open shifts (see database schema)
makes concurrent clock-ins fail closed. Timestamps are UTC.
Clock-out accepts latitude/longitude/location for form
compatibility but does not store them — clock-out location is
not recorded in the current schema, so do not treat clock-out
payloads as location evidence.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required, pagination_args

bp = Blueprint("attendance", __name__)


@bp.route("/attendance")
@login_required
def attendance():
    user = get_current_user()
    limit, offset = pagination_args()
    conn = get_db_connection()
    try:
        if is_privileged(user["role"]):
            rows = conn.execute(
                "SELECT * FROM attendance ORDER BY clock_in_time DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            users = conn.execute("SELECT email, full_name FROM users ORDER BY full_name").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE user_email = ? ORDER BY clock_in_time DESC LIMIT ? OFFSET ?",
                (user["email"], limit, offset),
            ).fetchall()
            users = []
        open_shift = conn.execute(
            "SELECT id FROM attendance WHERE user_email = ? AND clock_out_time IS NULL",
            (user["email"],),
        ).fetchone()
    finally:
        conn.close()
    markers = [
        {
            "lat": r["latitude"],
            "lon": r["longitude"],
            "name": r["location_name"],
            "email": r["user_email"],
        }
        for r in rows
        if r["latitude"] is not None and r["longitude"] is not None
    ]
    return render_template(
        "attendance.html",
        user=user,
        rows=[dict(r) for r in rows],
        users=[dict(u) for u in users],
        markers=markers,
        open_shift=bool(open_shift),
    )


@bp.route("/attendance/clock-in", methods=["POST"])
@login_required
def clock_in():
    user = get_current_user()
    try:
        latitude = float(request.form["latitude"])
        longitude = float(request.form["longitude"])
    except (KeyError, ValueError):
        flash("Latitude and longitude are required to clock in.", "error")
        return redirect(url_for("attendance.attendance"))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        flash("Latitude/longitude out of range.", "error")
        return redirect(url_for("attendance.attendance"))
    location_name = request.form.get("location_name", "Unknown") or "Unknown"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM attendance WHERE user_email = ? AND clock_out_time IS NULL",
            (user["email"],),
        ).fetchone()
        if existing:
            flash("You are already clocked in.", "error")
            return redirect(url_for("attendance.attendance"))
        try:
            conn.execute(
                "INSERT INTO attendance (user_email, clock_in_time, latitude, longitude, location_name)"
                " VALUES (?, ?, ?, ?, ?)",
                (user["email"], now, latitude, longitude, location_name),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Lost a race with another clock-in for the same user.
            flash("You are already clocked in.", "error")
    finally:
        conn.close()
    flash(f"Clocked in at {now} UTC.", "success")
    return redirect(url_for("attendance.attendance"))


@bp.route("/attendance/clock-out", methods=["POST"])
@login_required
def clock_out():
    user = get_current_user()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM attendance WHERE user_email = ? AND clock_out_time IS NULL"
            " ORDER BY clock_in_time DESC LIMIT 1",
            (user["email"],),
        ).fetchone()
        if not row:
            flash("No active clock-in found.", "error")
            return redirect(url_for("attendance.attendance"))
        conn.execute("UPDATE attendance SET clock_out_time = ? WHERE id = ?", (now, row["id"]))
        conn.commit()
    finally:
        conn.close()
    flash(f"Clocked out at {now} UTC.", "success")
    return redirect(url_for("attendance.attendance"))
