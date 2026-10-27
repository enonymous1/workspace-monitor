"""One shared HTTP client for the Streamlit frontend.

v1 duplicated ``API_BASE_URL`` and ``get_auth_headers()`` in every
page, and they drifted: the distance calculator read a different
session key (``token`` instead of ``auth_token``), so its requests
went out unauthenticated. Pages should import from here only.
"""

from __future__ import annotations

from typing import Any, Optional

import requests

from utils.config import API_BASE_URL, API_TIMEOUT_SECONDS


def get_auth_headers(token: Optional[str] = None) -> dict:
    """Authorization header for a token, or an empty dict without one."""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def api_get(endpoint: str, token: Optional[str] = None, params: Optional[dict] = None) -> Any:
    response = requests.get(
        f"{API_BASE_URL}/{endpoint}", headers=get_auth_headers(token), params=params, timeout=API_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()


def api_post(endpoint: str, payload: dict, token: Optional[str] = None) -> Any:
    response = requests.post(
        f"{API_BASE_URL}/{endpoint}", json=payload, headers=get_auth_headers(token), timeout=API_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()


def api_delete(endpoint: str, token: Optional[str] = None) -> Any:
    response = requests.delete(
        f"{API_BASE_URL}/{endpoint}", headers=get_auth_headers(token), timeout=API_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()
