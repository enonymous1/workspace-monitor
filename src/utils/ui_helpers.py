"""Shared Streamlit helpers: login state, sidebar, role helpers.

v2 changes from v1:

* ``login()`` now takes ``email`` + ``password`` and posts both to
  ``/api/login``. The v1 quick-access buttons that logged in as any
  role with no password are gone, as is the ``role`` argument.
* Tokens are no longer written to browser ``localStorage``. v1's
  rehydration script accepted unverified JSON posted back from
  localStorage and restored a session from it. Session state only
  in v2: closing the tab logs you out, which is the correct
  default for an HR/attendance app.
* Role comparisons are normalized through ``current_role()`` so
  ``"Admin"``/``"admin"`` drift cannot silently break admin views
  again (it did, in attendance, schedule, and mileage).
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.api_client import api_get, api_post, get_auth_headers  # noqa: E402


def current_role() -> str:
    """Session role normalized to 'Admin', 'Supervisor', or 'Standard'."""
    role = str(st.session_state.get("user_role") or "Standard")
    lowered = role.lower()
    if lowered == "admin":
        return "Admin"
    if lowered == "supervisor":
        return "Supervisor"
    return "Standard"


def is_admin() -> bool:
    return current_role() == "Admin"


def is_privileged() -> bool:
    return current_role() in ("Admin", "Supervisor")


def session_token() -> str:
    return str(st.session_state.get("auth_token") or "")


def auth_headers() -> dict:
    return get_auth_headers(session_token())


def fetch_data(endpoint: str, email: str | None = None):
    """Fetch from the backend with token auth; None on failure."""
    params = {}
    if email:
        params["email"] = email
    try:
        return api_get(endpoint, token=session_token(), params=params or None)
    except Exception:
        st.error(f"Failed to fetch data from {endpoint}. Is the backend running or is your session expired?")
        return None


def login(email: str, password: str) -> bool:
    """Log in with email + password. Returns True on success."""
    try:
        data = api_post("login", {"email": email, "password": password})
    except Exception as exc:
        st.error(f"Login failed: {exc}")
        return False
    st.session_state.is_logged_in = True
    st.session_state.user_role = data["role"]
    st.session_state.user_email = email
    st.session_state.user_name = data["full_name"]
    st.session_state.auth_token = data["access_token"]
    st.rerun()
    return True


def logout() -> None:
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.auth_token = None
    st.rerun()


def show_common_sidebar() -> None:
    if st.session_state.get("is_logged_in", False):
        st.sidebar.title(f"Role: {current_role()}")
        st.sidebar.info(f"Logged in as: {st.session_state.user_email}")
        if st.sidebar.button("Logout", key="sidebar_logout_btn_global", use_container_width=True):
            logout()
        st.sidebar.markdown("---")
    else:
        st.sidebar.warning("Please log in to continue.")


def enforce_login() -> None:
    """Block a page for anonymous visitors, with a way back to login."""
    if not st.session_state.get("is_logged_in", False):
        st.markdown(
            """
            <style>
                [data-testid="stSidebar"] { display: none; }
                [data-testid="stSidebarNav"] { display: none; }
                .login-enforce-container {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 60vh;
                    text-align: center;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="login-enforce-container">', unsafe_allow_html=True)
        st.warning("⚠️ Access Denied: Please log in first to access this page.")
        if st.button("🔑 Go to Login Screen", use_container_width=True, type="primary"):
            try:
                st.switch_page("app.py")
            except Exception:
                st.switch_page("frontend/app.py")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()
