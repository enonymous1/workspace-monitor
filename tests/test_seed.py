"""Seed determinism: seeding twice must not duplicate anything."""

from api.database import get_db_connection, seed_demo_data


def test_seed_is_idempotent(client):
    assert seed_demo_data() == 0
    conn = get_db_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 15
        # >=75: other tests may clock in/out against the same test DB.
        assert conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] >= 75
        assert conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] >= 17
    finally:
        conn.close()
