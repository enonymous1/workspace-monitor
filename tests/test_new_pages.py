"""New pages in v3.1: Users, Collateral, HR, Voice, Classroom."""

from __future__ import annotations

from conftest import login


def test_users_page_admin_only(client):
    login(client, "user@example.com")
    assert client.get("/users").status_code == 403
    login(client)
    html = client.get("/users").get_data(as_text=True)
    assert "Workspace Users" in html
    assert "admin@example.com" in html


def test_users_create_suspend_reactivate_and_reset(client):
    login(client)
    response = client.post(
        "/users/add",
        data={
            "email": "newhire@example.com",
            "full_name": "New Hire",
            "department": "Operations",
            "title": "Associate",
            "role": "Standard",
            "password": "Newpass123!",
        },
        follow_redirects=True,
    )
    assert "created" in response.get_data(as_text=True)
    # Standard user cannot create users.
    login(client, "user@example.com")
    assert (
        client.post(
            "/users/add",
            data={"email": "x@example.com", "full_name": "X", "password": "Newpass123!"},
        ).status_code
        == 403
    )
    login(client)
    # Suspend, then login fails, then reactivate. Log out first:
    # a logged-in admin visiting /login is redirected home.
    client.post("/users/suspend", data={"email": "newhire@example.com"}, follow_redirects=True)
    client.post("/logout")
    assert (
        client.post(
            "/login", data={"email": "newhire@example.com", "password": "Newpass123!"}
        ).status_code
        == 401
    )
    login(client)
    client.post("/users/reactivate", data={"email": "newhire@example.com"}, follow_redirects=True)
    # Admin reset, then new password works.
    client.post(
        "/users/reset-password",
        data={
            "email": "newhire@example.com",
            "new_password": "Resetpass123!",
            "confirm_password": "Resetpass123!",
        },
        follow_redirects=True,
    )
    response = client.post(
        "/login",
        data={"email": "newhire@example.com", "password": "Resetpass123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_admin_cannot_suspend_self(client):
    login(client)
    response = client.post(
        "/users/suspend", data={"email": "admin@example.com"}, follow_redirects=True
    )
    assert "cannot suspend your own" in response.get_data(as_text=True).lower()
    assert client.get("/").status_code == 200


def test_collateral_crud_and_mailout_reduces_stock(client):
    login(client)
    html = client.get("/collateral").get_data(as_text=True)
    assert "Spring mail-out pamphlet" in html
    assert "Below reorder level" in html
    client.post(
        "/collateral/add",
        data={
            "name": "Test Card",
            "item_type": "business card",
            "quantity": "100",
            "reorder_level": "10",
            "status": "printed",
        },
        follow_redirects=True,
    )
    html = client.get("/collateral").get_data(as_text=True)
    assert "Test Card" in html
    # Standard user cannot add.
    login(client, "user@example.com")
    assert (
        client.post(
            "/collateral/add",
            data={"name": "Nope", "item_type": "flyer", "quantity": "1", "status": "draft"},
        ).status_code
        == 403
    )
    login(client)
    # Mail-out for demo item 1 (250 on hand) reduces stock.
    client.post(
        "/collateral/mailout",
        data={"item_id": "1", "date": "2026-11-01", "recipient_count": "10"},
        follow_redirects=True,
    )
    html = client.get("/collateral").get_data(as_text=True)
    assert "240" in html
    # Item with mail-outs cannot be deleted.
    response = client.post("/collateral/delete/1", follow_redirects=True)
    assert "Cannot delete" in response.get_data(as_text=True)


def test_hr_roster_pay_admin_only_and_job_crud(client):
    login(client, "user@example.com")
    html = client.get("/hr").get_data(as_text=True)
    assert "Front Desk Associate" in html
    assert "<th>Pay-cycle hours</th>" not in html
    assert "user@example.com" in html
    assert "admin@example.com" not in html
    login(client)
    html = client.get("/hr").get_data(as_text=True)
    assert "<th>Pay-cycle hours</th>" in html
    assert "Indeed Employer Dashboard" in html
    client.post(
        "/hr/job/add",
        data={"title": "Test Role", "status": "open", "applications_count": "2"},
        follow_redirects=True,
    )
    assert "Test Role" in client.get("/hr").get_data(as_text=True)


def test_voice_manual_log_and_no_sync_claim(client):
    login(client)
    html = client.get("/voice").get_data(as_text=True)
    assert "No live sync" in html
    assert "Example Caller" in html
    client.post(
        "/voice/log",
        data={
            "date": "2026-11-02",
            "direction": "inbound",
            "contact": "Test Caller",
            "outcome": "Left message",
        },
        follow_redirects=True,
    )
    assert "Test Caller" in client.get("/voice").get_data(as_text=True)


def test_classroom_not_configured_and_standard_forbidden(client, monkeypatch):
    monkeypatch.delenv("WORKSPACE_MONITOR_CLASSROOM_TOKEN", raising=False)
    login(client, "user@example.com")
    assert client.get("/classroom").status_code == 403
    login(client)
    html = client.get("/classroom").get_data(as_text=True)
    assert "Not connected" in html
    assert "classroom.courses.readonly" in html


def test_classroom_mocked_api(monkeypatch, client):
    import workspace_monitor.classroom as classroom_module
    import workspace_monitor.routes.classroom as classroom_route

    monkeypatch.setenv("WORKSPACE_MONITOR_CLASSROOM_TOKEN", "fake-token")
    monkeypatch.setattr(
        classroom_route,
        "get_overview",
        lambda: (
            [
                {
                    "id": "c1",
                    "name": "Demo Training",
                    "coursework": [{"title": "Safety 101", "state": "PUBLISHED"}],
                }
            ],
            None,
        ),
    )
    # Route imports get_overview directly; the monkeypatch above
    # replaces it in the route module.
    login(client)
    html = client.get("/classroom").get_data(as_text=True)
    assert "Demo Training" in html
    assert "Safety 101" in html
    assert classroom_module.API_BASE.startswith("https://classroom.googleapis.com")
