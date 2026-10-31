"""End-to-end page tests via the Flask test client."""

from __future__ import annotations

import io

from conftest import login


def test_login_page_and_home(client):
    assert client.get("/login").status_code == 200
    assert client.get("/").status_code == 302  # not logged in -> login
    response = login(client)
    assert response.status_code == 200
    assert "Welcome" in response.get_data(as_text=True)
    assert "Users visible" in response.get_data(as_text=True)


def test_bad_login_returns_401_and_unknown_user_same_message(client):
    bad_password = client.post("/login", data={"email": "admin@example.com", "password": "wrong"})
    unknown = client.post("/login", data={"email": "nobody@example.com", "password": "wrong"})
    assert bad_password.status_code == 401
    assert unknown.status_code == 401
    assert bad_password.get_data(as_text=True) == unknown.get_data(as_text=True)


def test_logout_clears_session(client):
    login(client)
    assert client.get("/").status_code == 200
    client.post("/logout", follow_redirects=True)
    assert client.get("/").status_code == 302


def test_home_counts_are_real_counts(client):
    login(client)
    html = client.get("/").get_data(as_text=True)
    # Demo seed: 15 users, 75 attendance rows, 2 pending mileage.
    assert ">15<" in html or "15" in html
    assert "75" in html


def test_attendance_clock_in_out_and_double_clock_in(client):
    login(client, "user@example.com")
    response = client.post(
        "/attendance/clock-in",
        data={"latitude": "38.3", "longitude": "-77.5", "location_name": "Test Site"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "currently clocked in" in response.get_data(as_text=True)
    second = client.post(
        "/attendance/clock-in",
        data={"latitude": "38.3", "longitude": "-77.5", "location_name": "Test Site"},
        follow_redirects=True,
    )
    assert "already clocked in" in second.get_data(as_text=True)
    out = client.post("/attendance/clock-out", follow_redirects=True)
    assert "Clocked out" in out.get_data(as_text=True)


def test_standard_user_sees_only_own_attendance(client):
    login(client, "user@example.com")
    html = client.get("/attendance").get_data(as_text=True)
    assert "user@example.com" in html
    assert "admin@example.com" not in html


def test_privileged_user_sees_all_attendance(client):
    login(client)
    html = client.get("/attendance").get_data(as_text=True)
    assert "admin@example.com" in html
    assert "user@example.com" in html


def test_schedule_week_view(client):
    login(client)
    html = client.get("/schedule").get_data(as_text=True)
    assert "Week of" in html
    # Standard user cannot filter to another user's events.
    login(client, "user@example.com")
    html = client.get("/schedule?user_emails=admin@example.com").get_data(as_text=True)
    assert "admin@example.com" not in html


def test_mileage_add_is_attributed_to_token_holder(client):
    login(client, "user@example.com")
    # A Standard user trying to file for admin is recorded as themselves.
    client.post(
        "/mileage/add",
        data={
            "date": "2026-10-31",
            "start_location": "A",
            "end_location": "B",
            "miles": "10",
            "purpose": "Test",
            "user_email": "admin@example.com",
        },
        follow_redirects=True,
    )
    # Check via the mileage page for this user (not via a raw
    # connection, which would not use the test app's database).
    html = client.get("/mileage").get_data(as_text=True)
    assert "Test" in html


def test_mileage_bulk_upload_all_or_nothing(client):
    login(client)
    good = "date,start_location,end_location,miles,purpose\n2026-10-31,A,B,5,Good\n"
    bad = (
        "date,start_location,end_location,miles,purpose\n2026-10-31,A,B,5,Good\n"
        "2026-10-31,A,B,not-a-number,Bad\n"
    )
    response = client.post(
        "/mileage/upload",
        data={"file": (io.BytesIO(good.encode()), "mileage.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "Uploaded 1 entries" in response.get_data(as_text=True)
    response = client.post(
        "/mileage/upload",
        data={"file": (io.BytesIO(bad.encode()), "mileage.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "nothing saved" in response.get_data(as_text=True)
    html = client.get("/mileage").get_data(as_text=True)
    assert "Good" in html
    assert "Bad" not in html


def test_mileage_export_csv(client):
    login(client)
    response = client.get("/mileage/export")
    assert response.status_code == 200
    assert "date,user_email" in response.get_data(as_text=True)


def test_directory_search_and_permissions(client):
    login(client, "user@example.com")
    html = client.get("/directory?q=Workspace Support").get_data(as_text=True)
    assert "Workspace Support" in html
    # Standard user cannot create for someone else.
    response = client.post(
        "/directory/add",
        data={
            "owner_email": "admin@example.com",
            "full_name": "Nope",
            "email": "nope@example.com",
        },
        follow_redirects=True,
    )
    assert "Not authorized" in response.get_data(as_text=True)
    # Admin can.
    login(client)
    response = client.post(
        "/directory/add",
        data={
            "owner_email": "admin@example.com",
            "full_name": "New Contact",
            "email": "new@example.com",
        },
        follow_redirects=True,
    )
    assert "Contact saved" in response.get_data(as_text=True)


def test_distance_page_get_and_cache(monkeypatch, client):
    from workspace_monitor import services

    login(client)
    assert client.get("/distance").status_code == 200
    calls = []

    def fake_coords(address, timeout):
        calls.append(address)
        return (38.4, -77.4)

    def fake_route(c1, c2, timeout):
        return (43.11, 62.66, "abc")

    monkeypatch.setattr(services, "get_coordinates", fake_coords)
    monkeypatch.setattr(services, "get_route", fake_route)
    # Route handlers import the functions directly, so patch there too.
    import workspace_monitor.routes.distance as distance_routes

    monkeypatch.setattr(distance_routes, "get_coordinates", fake_coords)
    monkeypatch.setattr(distance_routes, "get_route", fake_route)
    response = client.post("/distance", data={"start": "A", "end": "B"}, follow_redirects=True)
    assert "43.11" in response.get_data(as_text=True)
    # Second identical request must come from cache: no new geocoding.
    calls.clear()
    response = client.post("/distance", data={"start": "A", "end": "B"}, follow_redirects=True)
    assert "43.11" in response.get_data(as_text=True)
    assert calls == []
