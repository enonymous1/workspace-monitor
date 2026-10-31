"""External services: Nominatim geocoding + OSRM routing, with
the local route cache. Ported from the v2 distance page, with
the same rules: 10 s timeouts, OSRM over HTTPS, successes
cached, failures never cached (a transient outage must not
poison the cache).
"""

from __future__ import annotations

import sqlite3

import polyline
import requests

HEADERS = {"User-Agent": "workspace-monitor/3.0", "Accept": "application/json"}


def get_coordinates(address: str, timeout: float) -> tuple[float, float] | None:
    """Geocode an address, or None if it cannot be found."""
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json", "limit": 1},
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def get_route(
    coords1: tuple[float, float], coords2: tuple[float, float], timeout: float
) -> tuple[float, float, str] | None:
    """Route between two (lat, lon) pairs, or None on failure."""
    lat1, lon1 = coords1
    lat2, lon2 = coords2
    response = requests.get(
        f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
        params={"overview": "full", "geometries": "polyline"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") != "Ok":
        return None
    route = data["routes"][0]
    return route["distance"] * 0.000621371, route["duration"] / 60, route["geometry"]


def get_cached_route(conn: sqlite3.Connection, addr_start: str, addr_end: str) -> dict | None:
    row = conn.execute(
        "SELECT distance_miles, duration_minutes, geometry_polyline FROM route_cache"
        " WHERE addr_start = ? AND addr_end = ?",
        (addr_start.strip().lower(), addr_end.strip().lower()),
    ).fetchone()
    return dict(row) if row else None


def save_route_to_cache(
    conn: sqlite3.Connection,
    addr_start: str,
    addr_end: str,
    distance_miles: float,
    duration_minutes: float,
    geometry_polyline: str,
) -> None:
    # A driving polyline is rarely over ~100 KB; cap it so a
    # client cannot stuff megabytes into SQLite.
    conn.execute(
        "INSERT OR REPLACE INTO route_cache (addr_start, addr_end, distance_miles, duration_minutes, geometry_polyline)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            addr_start.strip().lower(),
            addr_end.strip().lower(),
            distance_miles,
            duration_minutes,
            geometry_polyline[:1_000_000],
        ),
    )
    conn.commit()


def decode_polyline(geometry: str) -> list[list[float]]:
    """Decode an OSRM polyline to [[lat, lon], ...] for Leaflet."""
    try:
        return [[lat, lon] for lat, lon in polyline.decode(geometry)]
    except Exception:
        return []
