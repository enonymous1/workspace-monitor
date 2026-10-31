"""Security: CSRF, rate limiting, suspended users."""

from __future__ import annotations

from conftest import csrf_token, login

from workspace_monitor import create_app
from workspace_monitor.config import Settings
from workspace_monitor.database import seed_demo_data
from workspace_monitor.rate_limit import LoginRateLimiter


def test_csrf_required_when_testing_off(tmp_path):
    settings = Settings(
        secret_key="test-secret",
        db_path=tmp_path / "csrf.db",
        auto_seed=False,
        login_max_failures=1000,
        login_window_seconds=900,
        api_timeout_seconds=10,
        port=5000,
    )
    flask_app = create_app(settings)
    # TESTING stays False, so the CSRF check runs.
    seed_demo_data(settings.db_path)
    client = flask_app.test_client()
    no_token = client.post("/login", data={"email": "admin@example.com", "password": "Demo1234!"})
    assert no_token.status_code == 400
    token = csrf_token(client)
    ok = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "Demo1234!", "csrf_token": token},
        follow_redirects=True,
    )
    assert ok.status_code == 200


def test_rate_limiter_blocks_after_max_failures():
    limiter = LoginRateLimiter(max_failures=3, window_seconds=900)
    assert not limiter.is_blocked("1.2.3.4")
    limiter.record_failure("1.2.3.4")
    limiter.record_failure("1.2.3.4")
    assert not limiter.is_blocked("1.2.3.4")
    limiter.record_failure("1.2.3.4")
    assert limiter.is_blocked("1.2.3.4")
    limiter.record_success("1.2.3.4")
    assert not limiter.is_blocked("1.2.3.4")


def test_suspended_user_cannot_log_in(app, client):
    with app.app_context():
        from workspace_monitor.database import get_db_connection

        conn = get_db_connection()
        conn.execute("UPDATE users SET is_suspended = 1 WHERE email = 'user@example.com'")
        conn.commit()
        conn.close()
    response = login(client, "user@example.com")
    assert response.status_code == 401
