"""Test setup: point the API at a throwaway DB and a fixed secret.

These env vars must be set before ``api.main`` is imported, because
``api.database.DB_PATH`` and ``api.auth.SECRET_KEY`` are computed at
import time. Pytest loads conftest.py before test modules, so this
ordering holds.
"""

import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="workspace-monitor-test-"))
os.environ.setdefault("WORKSPACE_MONITOR_DB", str(_TMP / "test.db"))
os.environ.setdefault("WORKSPACE_MONITOR_SECRET_KEY", "test-secret-do-not-use-in-production")
os.environ.setdefault("WORKSPACE_MONITOR_DEMO_PASSWORD", "Demo1234!")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """TestClient that runs the app lifespan (schema + demo seed)."""
    with TestClient(app) as test_client:
        yield test_client


def _login(client, email, password="Demo1234!"):
    response = client.post("/api/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token(client):
    return _login(client, "admin@example.com")


@pytest.fixture(scope="module")
def standard_token(client):
    return _login(client, "user@example.com")


@pytest.fixture(scope="module")
def supervisor_token(client):
    return _login(client, "jane.doe@example.com")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
