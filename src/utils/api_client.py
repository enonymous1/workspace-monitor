"""One shared HTTP client for the Streamlit frontend.

v1 duplicated ``API_BASE_URL`` and ``get_auth_headers()`` in every
page, and they drifted: the distance calculator read a different
session key (``token`` instead of ``auth_token``), so its requests
went out unauthenticated. Pages should import from here only.

v2.1: errors are a typed ``ApiError`` carrying the backend's
``detail`` string when it gave one. v2.0 raised
``requests.HTTPError`` via ``raise_for_status()`` and discarded
the body, so callers could not tell "session expired" from
"backend down" — and pages fell back to showing raw exception
text to the user. Callers should catch ``ApiError`` and map
401 to a login prompt, everything else to a generic message.
"""

from __future__ import annotations

from typing import Any, Optional

import requests

from utils.config import API_BASE_URL, API_TIMEOUT_SECONDS


class ApiError(Exception):
    """An HTTP error with the backend's detail, when it gave one."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def get_auth_headers(token: Optional[str] = None) -> dict:
    """Authorization header for a token, or an empty dict without one."""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _raise_for(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        detail = response.json().get("detail", response.reason)
    except ValueError:
        # Non-JSON error page (proxy, 500 HTML): never crash on it.
        detail = response.reason or f"HTTP {response.status_code}"
    raise ApiError(response.status_code, str(detail))


def _request(method: str, endpoint: str, token: Optional[str], **kwargs: Any) -> Any:
    try:
        response = requests.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            headers=get_auth_headers(token),
            timeout=API_TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as exc:
        # Backend unreachable: status 0 distinguishes it from HTTP errors.
        raise ApiError(0, "Backend unreachable") from exc
    _raise_for(response)
    return response.json()


def api_get(endpoint: str, token: Optional[str] = None, params: Optional[dict] = None) -> Any:
    return _request("GET", endpoint, token, params=params)


def api_post(endpoint: str, payload: dict, token: Optional[str] = None) -> Any:
    return _request("POST", endpoint, token, json=payload)


def api_delete(endpoint: str, token: Optional[str] = None) -> Any:
    return _request("DELETE", endpoint, token)
