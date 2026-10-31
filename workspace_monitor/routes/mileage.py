"""Mileage: manual entry, bulk CSV/Excel upload, CSV export.

Bulk upload is one transaction: all rows are validated first,
then inserted together, so a bad row halfway through never
leaves a half-imported file (the v2 Streamlit upload sent one
HTTP request per row and reported only a success count).
``status`` is never accepted from a form: new entries are
always ``pending``. There is still no approve/reject action;
the status column reflects the stored value only.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import (
    get_current_user,
    login_required,
    pagination_args,
    visible_email,
)

bp = Blueprint("mileage", __name__)

REQUIRED_COLUMNS = {"date", "start_location", "end_location", "miles", "purpose"}


def _owner(user: dict, requested: str) -> str:
    """Privileged users may file for a named user; Standard users
    are always recorded as themselves (v2 trusted the form
    field, letting any user file for anyone)."""
    return requested if is_privileged(user["role"]) else user["email"]


def _parse_rows(raw_rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate upload rows; return (entries, errors)."""
    entries: list[dict] = []
    errors: list[str] = []
    for i, row in enumerate(raw_rows, start=1):
        try:
            miles = float(row["miles"])
            if miles <= 0:
                raise ValueError("miles must be positive")
            # Excel timestamps and date strings both normalize here;
            # v2 stored Excel timestamps as datetime strings.
            date_value = row["date"]
            if isinstance(date_value, datetime):
                date_str = date_value.date().isoformat()
            else:
                date_str = datetime.fromisoformat(str(date_value).strip()[:10]).date().isoformat()
            entries.append(
                {
                    "date": date_str,
                    "start_location": str(row["start_location"]).strip(),
                    "end_location": str(row["end_location"]).strip(),
                    "miles": miles,
                    "purpose": str(row["purpose"]).strip(),
                }
            )
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
    return entries, errors


def _read_upload(file_storage) -> list[dict]:
    filename = (file_storage.filename or "").lower()
    if filename.endswith(".csv"):
        text = file_storage.read().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    if filename.endswith((".xlsx", ".xls")):
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(file_storage.read()), data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [dict(zip(headers, row)) for row in rows[1:] if any(v is not None for v in row)]
    raise ValueError("Upload a .csv or .xlsx file.")


@bp.route("/mileage")
@login_required
def mileage():
    user = get_current_user()
    limit, offset = pagination_args()
    filter_email = visible_email(user, request.args.get("user_email") or None)
    conn = get_db_connection()
    try:
        if filter_email:
            rows = conn.execute(
                "SELECT * FROM mileage_log WHERE user_email = ? ORDER BY date DESC LIMIT ? OFFSET ?",
                (filter_email, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM mileage_log ORDER BY date DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        totals = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(miles), 0), SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END)"
            " FROM mileage_log" + (" WHERE user_email = ?" if filter_email else ""),
            (filter_email,) if filter_email else (),
        ).fetchone()
        all_users = (
            conn.execute("SELECT email, full_name FROM users ORDER BY full_name").fetchall()
            if is_privileged(user["role"])
            else []
        )
    finally:
        conn.close()
    return render_template(
        "mileage.html",
        user=user,
        rows=[dict(r) for r in rows],
        total_entries=totals[0],
        total_miles=totals[1],
        verified=totals[2],
        all_users=[dict(u) for u in all_users],
        filter_email=filter_email,
    )


@bp.route("/mileage/add", methods=["POST"])
@login_required
def add_mileage():
    user = get_current_user()
    entries, errors = _parse_rows(
        [
            {
                "date": request.form.get("date", ""),
                "start_location": request.form.get("start_location", ""),
                "end_location": request.form.get("end_location", ""),
                "miles": request.form.get("miles", ""),
                "purpose": request.form.get("purpose", ""),
            }
        ]
    )
    if errors:
        flash(errors[0], "error")
        return redirect(url_for("mileage.mileage"))
    entry = entries[0]
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO mileage_log (user_email, date, start_location, end_location, miles, purpose)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                _owner(user, request.form.get("user_email", user["email"])),
                entry["date"],
                entry["start_location"],
                entry["end_location"],
                entry["miles"],
                entry["purpose"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Mileage entry saved.", "success")
    return redirect(url_for("mileage.mileage"))


@bp.route("/mileage/upload", methods=["POST"])
@login_required
def upload_mileage():
    user = get_current_user()
    file_storage = request.files.get("file")
    if file_storage is None or not file_storage.filename:
        flash("Choose a CSV or Excel file to upload.", "error")
        return redirect(url_for("mileage.mileage"))
    try:
        raw_rows = _read_upload(file_storage)
    except Exception as exc:
        flash(f"Could not read file: {exc}", "error")
        return redirect(url_for("mileage.mileage"))
    if raw_rows and not REQUIRED_COLUMNS.issubset({str(k).strip() for k in raw_rows[0].keys()}):
        missing = sorted(REQUIRED_COLUMNS - {str(k).strip() for k in raw_rows[0].keys()})
        flash(f"Missing required columns: {', '.join(missing)}", "error")
        return redirect(url_for("mileage.mileage"))
    entries, errors = _parse_rows(raw_rows)
    if errors:
        flash(f"Upload rejected, nothing saved. {errors[0]}", "error")
        return redirect(url_for("mileage.mileage"))
    owner = _owner(user, request.form.get("user_email", user["email"]))
    conn = get_db_connection()
    try:
        for entry in entries:
            conn.execute(
                "INSERT INTO mileage_log (user_email, date, start_location, end_location, miles, purpose)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    owner,
                    entry["date"],
                    entry["start_location"],
                    entry["end_location"],
                    entry["miles"],
                    entry["purpose"],
                ),
            )
        conn.commit()
    finally:
        conn.close()
    flash(f"Uploaded {len(entries)} entries.", "success")
    return redirect(url_for("mileage.mileage"))


@bp.route("/mileage/export")
@login_required
def export_mileage():
    user = get_current_user()
    filter_email = visible_email(user, request.args.get("user_email") or None)
    conn = get_db_connection()
    try:
        if filter_email:
            rows = conn.execute(
                "SELECT date, user_email, start_location, end_location, miles, purpose, status"
                " FROM mileage_log WHERE user_email = ? ORDER BY date DESC",
                (filter_email,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, user_email, start_location, end_location, miles, purpose, status"
                " FROM mileage_log ORDER BY date DESC"
            ).fetchall()
    finally:
        conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["date", "user_email", "start_location", "end_location", "miles", "purpose", "status"]
    )
    writer.writerows([tuple(r) for r in rows])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=mileage.csv"},
    )
