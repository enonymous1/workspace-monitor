"""Distance calculator: Nominatim geocoding + OSRM routing.

Results are cached in the backend database, so a repeated
lookup never re-hits the public demo endpoints. These are
public demo endpoints with a usage policy (roughly 1
request/second, identifying User-Agent) — suitable for the
demo, not a production routing dependency. The route polyline
is rendered with Leaflet in the browser; the numbers in the
banner are server-computed, not client estimates.
"""

from __future__ import annotations

import requests
from flask import Blueprint, current_app, flash, render_template, request

from workspace_monitor.database import get_db_connection
from workspace_monitor.helpers import get_current_user, login_required
from workspace_monitor.services import (
    decode_polyline,
    get_cached_route,
    get_coordinates,
    get_route,
    save_route_to_cache,
)

bp = Blueprint("distance", __name__)


@bp.route("/distance", methods=["GET", "POST"])
@login_required
def distance():
    user = get_current_user()
    result = None
    start = (
        request.form.get("start", "Stafford Courthouse, VA")
        if request.method == "POST"
        else "Stafford Courthouse, VA"
    )
    end = (
        request.form.get("end", "Culpeper Courthouse, VA")
        if request.method == "POST"
        else "Culpeper Courthouse, VA"
    )
    if request.method == "POST":
        timeout = current_app.config["WM_TIMEOUT"]
        conn = get_db_connection()
        try:
            cached = get_cached_route(conn, start, end)
            if cached:
                result = {
                    "distance_miles": cached["distance_miles"],
                    "duration_minutes": cached["duration_minutes"],
                    "coords": decode_polyline(cached["geometry_polyline"]),
                    "methodology": "Retrieved from Route Cache Database",
                }
            else:
                try:
                    coords1 = get_coordinates(start, timeout)
                    coords2 = get_coordinates(end, timeout) if coords1 else None
                    route = get_route(coords1, coords2, timeout) if coords1 and coords2 else None
                except requests.RequestException as exc:
                    flash(f"Routing request failed: {exc}", "error")
                    route = None
                if route:
                    distance_miles, duration_minutes, geometry = route
                    save_route_to_cache(
                        conn, start, end, distance_miles, duration_minutes, geometry
                    )
                    result = {
                        "distance_miles": distance_miles,
                        "duration_minutes": duration_minutes,
                        "coords": decode_polyline(geometry),
                        "methodology": "Calculated via Nominatim + OSRM",
                    }
                else:
                    flash("Could not calculate a route for those addresses.", "error")
        finally:
            conn.close()
    return render_template("distance.html", user=user, start=start, end=end, result=result)
