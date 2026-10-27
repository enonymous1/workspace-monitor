"""Streamlit entry point: sign-in + home dashboard.

v2: sign-in requires email + password (v1 accepted an email alone
and offered one-click logins as any role). The home page is no
longer a stub: it shows live counts from the API when the backend
is reachable, and says so plainly when it is not.
"""

import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.config import PROJECT_ICON, PROJECT_TITLE  # noqa: E402
from utils.ui_helpers import current_role, fetch_data, login, show_common_sidebar  # noqa: E402

st.set_page_config(
    page_title=PROJECT_TITLE,
    page_icon=PROJECT_ICON,
    layout="wide",
)

if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.auth_token = None
    st.session_state.current_page_key = "home"

if not st.session_state.is_logged_in:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none; }
            [data-testid="stSidebarNav"] { display: none; }
            [data-testid="stHeader"] { display: none; }
            [data-testid="stAppViewBlockContainer"] { padding-top: 0rem; }
            .main > div {
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }
            .stButton > button { width: 100%; border-radius: 8px; height: 3em; font-weight: 600; }
            .login-card { padding: 2rem; border-radius: 12px; max-width: 450px; width: 100%; }
            @media (max-width: 640px) { .main > div { padding: 1rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_landing_page():
    with st.container():
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.subheader("Workspace Sign In")
        st.write("Enter your credentials to access the Virginia Hub.")
        demo_email = st.text_input("User Email", value="admin@example.com", key="login_email_input")
        demo_password = st.text_input("Password", type="password", key="login_password_input")
        if st.button("🔐 Sign In", key="login_primary_btn", use_container_width=True, type="primary"):
            login(email=demo_email, password=demo_password)
        with st.expander("🛠️ Demo credentials (demo data only)"):
            st.caption(
                "The demo seed creates 15 fictional @example.com users, all with "
                "password Demo1234! (override with WORKSPACE_MONITOR_DEMO_PASSWORD "
                "before seeding). Never seed demo data in production."
            )
            st.code("admin@example.com / Demo1234!")
        st.markdown("</div>", unsafe_allow_html=True)


def show_dashboard():
    st.session_state.current_page_key = "home"
    show_common_sidebar()
    user_name = st.session_state.get("user_name")
    user_email = st.session_state.get("user_email", "User")
    greeting_name = user_name if user_name and user_name != "None" else user_email
    st.title(f"👋 Welcome, {greeting_name}!")
    st.caption(f"Status: Logged in as **{current_role()}**")
    st.write("---")

    users = fetch_data("users")
    attendance = fetch_data("attendance")
    mileage = fetch_data("mileage")
    if users is None and attendance is None and mileage is None:
        st.warning("Backend unreachable. Start it with `python run_app.py`, then reload.")
        return
    col1, col2, col3 = st.columns(3)
    col1.metric("Users visible", len(users) if users else 0)
    col2.metric("Attendance records", len(attendance) if attendance else 0)
    pending = len([m for m in (mileage or []) if m.get("status") == "pending"])
    col3.metric("Mileage entries pending", pending)
    st.write("Use the sidebar pages for Attendance, Schedule, Mileage, Directory, and Distance Calculator.")


if not st.session_state.is_logged_in:
    show_landing_page()
else:
    show_dashboard()
