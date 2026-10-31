"""The shared frontend client: one header helper, no per-page drift."""

import pytest

from utils.api_client import ApiError, _raise_for, get_auth_headers


class _FakeResponse:
    def __init__(self, status_code, reason, body=None):
        self.status_code = status_code
        self.reason = reason
        self._body = body
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._body is None:
            raise ValueError("no JSON")
        return self._body


def test_auth_headers_with_token():
    assert get_auth_headers("abc123") == {"Authorization": "Bearer abc123"}


def test_auth_headers_without_token():
    assert get_auth_headers(None) == {}
    assert get_auth_headers("") == {}


def test_raise_for_keeps_backend_detail():
    with pytest.raises(ApiError) as exc_info:
        _raise_for(_FakeResponse(401, "Unauthorized", {"detail": "Invalid or expired token"}))
    assert exc_info.value.status == 401
    assert exc_info.value.detail == "Invalid or expired token"


def test_raise_for_non_json_error_does_not_crash():
    with pytest.raises(ApiError) as exc_info:
        _raise_for(_FakeResponse(500, "Internal Server Error"))
    assert exc_info.value.status == 500
    assert exc_info.value.detail == "Internal Server Error"


def test_raise_for_ok_response_is_silent():
    _raise_for(_FakeResponse(200, "OK", {"status": "ok"}))
