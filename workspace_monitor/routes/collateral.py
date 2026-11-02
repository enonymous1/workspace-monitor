"""Collateral: pamphlets, business cards, flyers, and mail-outs.

Local CRUD only, same pattern as Directory. Privileged users
(Admin/Supervisor) manage items and mail-outs; Standard users
read. An item with mail-outs cannot be deleted, so mail-out
history never loses the item it refers to.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from workspace_monitor.auth import is_privileged
from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required

bp = Blueprint("collateral", __name__)

ITEM_TYPES = ["pamphlet", "business card", "flyer", "other"]
STATUSES = ["draft", "printed", "distributed", "archived"]


def _require_privileged(user):
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")


def _float_or_none(value: str):
    try:
        return float(value) if value.strip() else None
    except ValueError:
        return None


@bp.route("/collateral")
@login_required
def collateral():
    user = get_current_user()
    conn = get_db_connection()
    try:
        items = conn.execute("SELECT * FROM collateral_items ORDER BY name ASC").fetchall()
        mailouts = conn.execute(
            "SELECT m.*, c.name AS item_name FROM mailouts m"
            " JOIN collateral_items c ON c.id = m.item_id ORDER BY m.date DESC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    low_stock = [dict(i) for i in items if i["quantity"] <= i["reorder_level"]]
    return render_template(
        "collateral.html",
        user=user,
        items=[dict(i) for i in items],
        mailouts=[dict(m) for m in mailouts],
        low_stock=low_stock,
        item_types=ITEM_TYPES,
        statuses=STATUSES,
        can_manage=is_privileged(user["role"]),
    )


@bp.route("/collateral/add", methods=["POST"])
@login_required
def add_item():
    user = get_current_user()
    _require_privileged(user)
    name = request.form.get("name", "").strip()
    item_type = request.form.get("item_type", "other")
    status = request.form.get("status", "draft")
    if not name or item_type not in ITEM_TYPES or status not in STATUSES:
        flash("Name, a valid type, and a valid status are required.", "error")
        return redirect(url_for("collateral.collateral"))
    try:
        quantity = int(request.form.get("quantity", "0"))
        reorder_level = int(request.form.get("reorder_level", "0"))
    except ValueError:
        flash("Quantity and reorder level must be whole numbers.", "error")
        return redirect(url_for("collateral.collateral"))
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO collateral_items (name, item_type, quantity, reorder_level, unit_cost, vendor, status, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                item_type,
                quantity,
                reorder_level,
                _float_or_none(request.form.get("unit_cost", "")),
                request.form.get("vendor", "").strip(),
                status,
                request.form.get("notes", "").strip(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash(f"Collateral item {name} saved.", "success")
    return redirect(url_for("collateral.collateral"))


@bp.route("/collateral/update/<int:item_id>", methods=["POST"])
@login_required
def update_item(item_id: int):
    user = get_current_user()
    _require_privileged(user)
    try:
        quantity = int(request.form.get("quantity", "0"))
        reorder_level = int(request.form.get("reorder_level", "0"))
    except ValueError:
        flash("Quantity and reorder level must be whole numbers.", "error")
        return redirect(url_for("collateral.collateral"))
    status = request.form.get("status", "draft")
    if status not in STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("collateral.collateral"))
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE collateral_items SET quantity = ?, reorder_level = ?, unit_cost = ?, vendor = ?, status = ?, notes = ?"
            " WHERE id = ?",
            (
                quantity,
                reorder_level,
                _float_or_none(request.form.get("unit_cost", "")),
                request.form.get("vendor", "").strip(),
                status,
                request.form.get("notes", "").strip(),
                item_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Collateral item updated.", "success")
    return redirect(url_for("collateral.collateral"))


@bp.route("/collateral/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_item(item_id: int):
    user = get_current_user()
    _require_privileged(user)
    conn = get_db_connection()
    try:
        mailout_count = conn.execute(
            "SELECT COUNT(*) FROM mailouts WHERE item_id = ?", (item_id,)
        ).fetchone()[0]
        if mailout_count:
            flash("Cannot delete an item with mail-out history. Archive it instead.", "error")
            return redirect(url_for("collateral.collateral"))
        conn.execute("DELETE FROM collateral_items WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()
    flash("Collateral item deleted.", "success")
    return redirect(url_for("collateral.collateral"))


@bp.route("/collateral/mailout", methods=["POST"])
@login_required
def add_mailout():
    user = get_current_user()
    _require_privileged(user)
    try:
        item_id = int(request.form.get("item_id", "0"))
        recipient_count = int(request.form.get("recipient_count", "0"))
    except ValueError:
        flash("Item and recipient count are required.", "error")
        return redirect(url_for("collateral.collateral"))
    date = request.form.get("date", "").strip()
    if not date or recipient_count < 0:
        flash("A date and a non-negative recipient count are required.", "error")
        return redirect(url_for("collateral.collateral"))
    conn = get_db_connection()
    try:
        item = conn.execute(
            "SELECT id, quantity FROM collateral_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("collateral.collateral"))
        conn.execute(
            "INSERT INTO mailouts (item_id, date, recipient_count, cost, notes) VALUES (?, ?, ?, ?, ?)",
            (
                item_id,
                date,
                recipient_count,
                _float_or_none(request.form.get("cost", "")),
                request.form.get("notes", "").strip(),
            ),
        )
        # A mail-out consumes stock; never let it go negative here.
        conn.execute(
            "UPDATE collateral_items SET quantity = MAX(0, quantity - ?) WHERE id = ?",
            (recipient_count, item_id),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Mail-out recorded.", "success")
    return redirect(url_for("collateral.collateral"))
