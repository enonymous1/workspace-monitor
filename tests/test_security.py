"""v2.1 security and correctness tests: revocation, stats, bulk, HR derivation."""

import jwt
from conftest import _login, auth_headers

from api.auth import ALGORITHM, SECRET_KEY


def test_logout_revokes_token(client):
    # Fresh login, not the module-shared admin_token fixture: revoking
    # the shared token would break every later test in this file.
    headers = auth_headers(_login(client, "admin@example.com"))
    assert client.get("/api/users", headers=headers).status_code == 200
    assert client.post("/api/logout", headers=headers).status_code == 200
    # The same token must stop working immediately, not at expiry.
    assert client.get("/api/users", headers=headers).status_code == 401


def test_pre_v21_token_without_jti_is_rejected(client):
    # Tokens issued before v2.1 have no jti and therefore cannot be
    # revoked; they are rejected outright (they expire within 8h).
    token = jwt.encode(
        {"sub": "admin@example.com", "role": "Admin"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert client.get("/api/users", headers=auth_headers(token)).status_code == 401


def test_stats_counts(client, admin_token):
    stats = client.get("/api/stats", headers=auth_headers(admin_token)).json()
    assert stats["users"] == 15
    assert stats["attendance_records"] >= 75
    assert stats["pending_mileage"] >= 0
    # Standard users get their own counts, not everyone's.
    user_stats = client.get(
        "/api/stats", headers=auth_headers(_login(client, "user@example.com"))
    ).json()
    assert user_stats["users"] == 1
    assert user_stats["attendance_records"] >= 5


def test_schedule_date_filter(client, admin_token):
    headers = auth_headers(admin_token)
    all_events = client.get("/api/schedule?limit=500", headers=headers).json()
    assert all_events
    # A single-day window must return only events on that day.
    day = all_events[0]["start_time"][:10]
    filtered = client.get(f"/api/schedule?start={day}&end={day}&limit=500", headers=headers).json()
    assert filtered
    assert all(e["start_time"][:10] == day for e in filtered)
    assert len(filtered) < len(all_events)


def test_mileage_bulk_insert_and_status_forbidden(client, standard_token):
    headers = auth_headers(standard_token)
    payload = {
        "entries": [
            {
                "user_email": "user@example.com",
                "date": "2026-02-01",
                "start_location": "Office",
                "end_location": "Site",
                "miles": 10.0,
                "purpose": "Bulk trip one",
            },
            {
                "user_email": "user@example.com",
                "date": "2026-02-02",
                "start_location": "Office",
                "end_location": "Site",
                "miles": 12.0,
                "purpose": "Bulk trip two",
            },
        ]
    }
    response = client.post("/api/mileage/bulk", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["inserted"] == 2
    mine = client.get("/api/mileage", headers=headers).json()
    assert any(m["purpose"] == "Bulk trip two" for m in mine)
    # Posting a status is now a 422, not a silent drop to pending.
    bad = dict(payload["entries"][0])
    bad["status"] = "verified"
    assert client.post("/api/mileage", json=bad, headers=headers).status_code == 422
    # And a bad date is a 422, not a stored string.
    bad_date = dict(payload["entries"][0])
    bad_date["date"] = "not-a-date"
    assert client.post("/api/mileage", json=bad_date, headers=headers).status_code == 422


def test_hr_clock_status_derived_from_attendance(client):
    from conftest import _login

    token = _login(client, "david.m@example.com")
    headers = auth_headers(token)
    hr = client.get(
        "/api/hr-status", headers=auth_headers(_login(client, "admin@example.com"))
    ).json()
    robert = next(h for h in hr if h["primary_email"] == "david.m@example.com")
    assert robert["clock_in_status"] is False
    payload = {"latitude": 38.0293, "longitude": -78.4767, "location_name": "Test HQ"}
    assert client.post("/api/attendance/clock-in", json=payload, headers=headers).status_code == 200
    hr = client.get(
        "/api/hr-status", headers=auth_headers(_login(client, "admin@example.com"))
    ).json()
    robert = next(h for h in hr if h["primary_email"] == "david.m@example.com")
    assert robert["clock_in_status"] is True
    assert (
        client.post("/api/attendance/clock-out", json=payload, headers=headers).status_code == 200
    )
    hr = client.get(
        "/api/hr-status", headers=auth_headers(_login(client, "admin@example.com"))
    ).json()
    robert = next(h for h in hr if h["primary_email"] == "david.m@example.com")
    assert robert["clock_in_status"] is False


def test_login_updates_last_login_time(client):
    from api.database import get_db_connection

    before = (
        get_db_connection()
        .execute("SELECT last_login_time FROM users WHERE email = 'user@example.com'")
        .fetchone()[0]
    )
    _login(client, "user@example.com")
    after = (
        get_db_connection()
        .execute("SELECT last_login_time FROM users WHERE email = 'user@example.com'")
        .fetchone()[0]
    )
    assert after != before


def test_open_shift_unique_index_exists():
    from api.database import get_db_connection

    indexes = (
        get_db_connection()
        .execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'attendance'")
        .fetchall()
    )
    names = {row[0] for row in indexes}
    assert "idx_attendance_open_shift" in names
    assert "idx_attendance_user" in names
