"""API behaviour tests: auth, role visibility, and the v1 bug fixes."""

from conftest import auth_headers


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_login_wrong_password_is_401(client):
    response = client.post("/api/login", json={"email": "admin@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_user_is_401_not_404(client):
    # Same status as a wrong password: no user enumeration.
    response = client.post("/api/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert response.status_code == 401


def test_v1_forged_token_is_rejected(client):
    # v1 accepted the literal string "email:role" as a token.
    response = client.get("/api/users", headers={"Authorization": "Bearer admin@example.com:Admin"})
    assert response.status_code == 401


def test_missing_token_is_rejected(client):
    assert client.get("/api/users").status_code == 401


def test_tampered_token_is_rejected(client, admin_token):
    tampered = admin_token[:-2] + "xx"
    assert client.get("/api/users", headers=auth_headers(tampered)).status_code == 401


def test_admin_sees_all_users_and_pagination(client, admin_token):
    all_users = client.get("/api/users", headers=auth_headers(admin_token)).json()
    assert len(all_users) == 15
    assert "password_hash" not in all_users[0]
    page = client.get("/api/users?limit=2", headers=auth_headers(admin_token)).json()
    assert len(page) == 2


def test_standard_user_sees_only_themselves(client, standard_token):
    users = client.get("/api/users", headers=auth_headers(standard_token)).json()
    assert [u["email"] for u in users] == ["user@example.com"]
    # A filter parameter cannot widen a Standard user's view.
    filtered = client.get("/api/users?email=admin@example.com", headers=auth_headers(standard_token)).json()
    assert [u["email"] for u in filtered] == ["user@example.com"]


def test_standard_attendance_is_own_only(client, standard_token):
    rows = client.get("/api/attendance", headers=auth_headers(standard_token)).json()
    assert rows and all(r["user_email"] == "user@example.com" for r in rows)


def test_supervisor_sees_all_attendance(client, supervisor_token):
    rows = client.get("/api/attendance", headers=auth_headers(supervisor_token)).json()
    emails = {r["user_email"] for r in rows}
    assert len(emails) > 1


def test_clock_in_duplicate_and_out(client):
    from conftest import _login

    token = _login(client, "robert.p@example.com")
    headers = auth_headers(token)
    payload = {"latitude": 38.0293, "longitude": -78.4767, "location_name": "Test HQ"}
    assert client.post("/api/attendance/clock-in", json=payload, headers=headers).status_code == 200
    assert client.post("/api/attendance/clock-in", json=payload, headers=headers).status_code == 400
    assert client.post("/api/attendance/clock-out", json=payload, headers=headers).status_code == 200
    assert client.post("/api/attendance/clock-out", json=payload, headers=headers).status_code == 400


def test_clock_coordinates_are_validated(client, standard_token):
    payload = {"latitude": 500.0, "longitude": 0.0, "location_name": "Nowhere"}
    assert client.post("/api/attendance/clock-in", json=payload, headers=auth_headers(standard_token)).status_code == 422


def test_mileage_spoof_is_blocked(client, standard_token, admin_token):
    # v1 stored request.user_email verbatim. A Standard user filing
    # under the admin's email must land under their own email instead.
    payload = {
        "user_email": "admin@example.com",
        "date": "2026-01-15",
        "start_location": "Office",
        "end_location": "Client",
        "miles": 9.5,
        "purpose": "Spoof test trip",
    }
    assert client.post("/api/mileage", json=payload, headers=auth_headers(standard_token)).status_code == 200
    mine = client.get("/api/mileage", headers=auth_headers(standard_token)).json()
    assert any(m["purpose"] == "Spoof test trip" and m["user_email"] == "user@example.com" for m in mine)
    admins = client.get(
        "/api/mileage?user_email=admin@example.com", headers=auth_headers(admin_token)
    ).json()
    assert not any(m["purpose"] == "Spoof test trip" for m in admins)


def test_admin_can_create_contact_for_other_and_standard_cannot(client, admin_token, standard_token):
    payload = {
        "owner_email": "someone-else@example.com",
        "full_name": "Other Person",
        "job_title": "Tester",
        "email": "other-person@example.com",
        "phone": "555-9999",
        "category": "Client",
    }
    # v1 denied real Admins here (lowercase "admin" comparison).
    assert client.post("/api/contacts", json=payload, headers=auth_headers(admin_token)).status_code == 200
    assert client.post("/api/contacts", json=payload, headers=auth_headers(standard_token)).status_code == 403
    contacts = client.get("/api/contacts", headers=auth_headers(admin_token)).json()
    contact = next(c for c in contacts if c["email"] == "other-person@example.com")
    assert client.delete(f"/api/contacts/{contact['id']}", headers=auth_headers(admin_token)).status_code == 200
    assert client.delete(f"/api/contacts/{contact['id']}", headers=auth_headers(admin_token)).status_code == 404


def test_standard_can_create_contact_for_themselves(client, standard_token):
    payload = {
        "owner_email": "user@example.com",
        "full_name": "My Own Contact",
        "job_title": "Self",
        "email": "my-own-contact@example.com",
        "phone": "555-8888",
        "category": "Team",
    }
    assert client.post("/api/contacts", json=payload, headers=auth_headers(standard_token)).status_code == 200


def test_route_cache_roundtrip(client, admin_token):
    headers = auth_headers(admin_token)
    assert client.get("/api/route-cache?addr_start=Nowhere&addr_end=Elsewhere", headers=headers).json() is None
    payload = {
        "addr_start": "Nowhere",
        "addr_end": "Elsewhere",
        "distance_miles": 12.5,
        "duration_minutes": 20.0,
        "geometry_polyline": "abc",
    }
    assert client.post("/api/route-cache", json=payload, headers=headers).status_code == 200
    cached = client.get("/api/route-cache?addr_start=nowhere&addr_end=elsewhere", headers=headers).json()
    assert cached["distance_miles"] == 12.5
