"""The shared frontend client: one header helper, no per-page drift."""

from utils.api_client import get_auth_headers


def test_auth_headers_with_token():
    assert get_auth_headers("abc123") == {"Authorization": "Bearer abc123"}


def test_auth_headers_without_token():
    assert get_auth_headers(None) == {}
    assert get_auth_headers("") == {}
