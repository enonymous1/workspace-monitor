"""Seed data: deterministic counts carried over from v2."""

from __future__ import annotations

from workspace_monitor.database import get_db_connection


def test_seed_counts(app):
    with app.app_context():
        conn = get_db_connection()
        try:
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 15
            assert conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 75
            assert conn.execute("SELECT COUNT(*) FROM mileage_log").fetchone()[0] == 4
            # Seeding again is a no-op.
            from workspace_monitor.database import seed_demo_data

            assert seed_demo_data(app.config["WM_DB_PATH"]) == 0
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 15
        finally:
            conn.close()


def test_demo_users_are_fictional(app):
    with app.app_context():
        conn = get_db_connection()
        try:
            emails = [row[0] for row in conn.execute("SELECT email FROM users")]
        finally:
            conn.close()
    assert all(email.endswith("@example.com") for email in emails)
