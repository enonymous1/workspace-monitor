"""Pytest fixtures: one throwaway Flask app + database per test.

The app is built with an explicit Settings object (temp DB,
fixed secret), so no test ever touches the developer's real
database. CSRF is enforced in the app, but Flask's TESTING
mode skips the check here — CSRF itself is covered by a
dedicated test that builds an app with TESTING off.
"""

from __future__ import annotations

import re

import pytest

from workspace_monitor import create_app
from workspace_monitor.config import Settings
from workspace_monitor.database import seed_demo_data


@pytest.fixture()
def app(tmp_path):
    settings = Settings(
        secret_key="test-secret-do-not-use-in-production",
        db_path=tmp_path / "test.db",
        auto_seed=False,
        login_max_failures=5,
        login_window_seconds=900,
        api_timeout_seconds=10,
        port=5000,
    )
    flask_app = create_app(settings)
    flask_app.config["TESTING"] = True
    seed_demo_data(settings.db_path)
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email="admin@example.com", password="Demo1234!"):
    """Log in via the real form; returns the response.

    Logs out first: a logged-in user visiting /login is
    redirected home (by design), so a second login call
    without a logout would silently stay as the first user.
    """
    client.post("/logout")
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def csrf_token(client, path="/login"):
    """Extract the CSRF token from a form page (for non-TESTING apps)."""
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, f"No CSRF token on {path}"
    return match.group(1)
