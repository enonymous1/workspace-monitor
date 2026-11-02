"""Classroom overview: read-only, Admin/Supervisor only.

Student and training data is sensitive, so Standard users
do not see this page at all. When no token is configured
the page is a setup guide, not a fake dashboard — see
classroom.py for how the token is supplied and why it is
never stored in the repo or the database.
"""

from __future__ import annotations

from flask import Blueprint, abort, render_template

from workspace_monitor.auth import is_privileged
from workspace_monitor.classroom import get_overview
from workspace_monitor.helpers import get_current_user, login_required

bp = Blueprint("classroom", __name__)


@bp.route("/classroom")
@login_required
def classroom():
    user = get_current_user()
    if not is_privileged(user["role"]):
        abort(403, "Admin or Supervisor only")
    courses, error = get_overview()
    return render_template("classroom.html", user=user, courses=courses, error=error)
