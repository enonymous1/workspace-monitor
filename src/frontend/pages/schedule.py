import datetime
import os
import sys

import pandas as pd
import streamlit as st
from streamlit_calendar import calendar

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.api_client import api_get
from utils.ui_helpers import current_role, enforce_login, fetch_data, show_common_sidebar

st.set_page_config(
    page_title="Workspace Schedule Dashboard",
    page_icon="📅",
    layout="wide",
)

# Auth Check
enforce_login()

st.session_state.current_page_key = "schedule"
show_common_sidebar()

st.title("📅 Workspace Schedule & Calendar")

# --- Setup Date Ranges ---
if "view_date" not in st.session_state:
    st.session_state.view_date = datetime.date.today()


# No @st.cache_data here: a cached response can outlive a session and
# serve stale 401s after re-login (the same reason attendance is uncached).
def fetch_schedule(emails=None):
    try:
        params = {"user_emails": emails} if emails else None
        return api_get("schedule", token=st.session_state.get("auth_token", ""), params=params)
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")
        return []


# --- Navigation / View Settings ---
# Read the persisted radio value first: on the rerun triggered by a
# Previous/Next click, the radio widget below has not run yet.
view_type = st.session_state.get("schedule_view_mode", "Week")
col_nav, col_view = st.columns([2, 1])

with col_nav:
    st.write("### Navigation")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    if c1.button("⬅️ Previous", key="schedule_prev_btn"):
        if view_type == "Week":
            st.session_state.view_date -= datetime.timedelta(days=7)
        else:
            # Move to previous month
            first = st.session_state.view_date.replace(day=1)
            st.session_state.view_date = (first - datetime.timedelta(days=1)).replace(day=1)
    if c2.button("Today", key="schedule_today_btn"):
        st.session_state.view_date = datetime.date.today()
    if c3.button("Next ➡️", key="schedule_next_btn"):
        if view_type == "Week":
            st.session_state.view_date += datetime.timedelta(days=7)
        else:
            # Move to next month
            first = st.session_state.view_date.replace(day=1)
            st.session_state.view_date = (first + datetime.timedelta(days=32)).replace(day=1)
    with c4:
        view_type = st.radio(
            "Display Mode", ["Week", "Month"], horizontal=True, key="schedule_view_mode"
        )

with col_view:
    st.write("### Current Perspective")
    st.markdown(f"🗓️ **Focus Date:** `{st.session_state.view_date.strftime('%Y-%m-%d')}`")

st.divider()

# --- Filters (Admin only) ---
selected_emails = None

if current_role() == "Admin":
    st.subheader("👥 Organize Attendance View (Multi-Select)")
    users_data = fetch_data("users") or []
    all_users = [u["email"] for u in users_data]
    selected_emails = st.multiselect("Filter for specific users:", all_users, default=None)

# --- Fetch and Filter Data ---
schedule_data = fetch_schedule(selected_emails)

if not schedule_data:
    st.write("No schedule entries found.")
else:
    df = pd.DataFrame(schedule_data)
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])

    # Map types to FullCalendar compatible event objects
    calendar_events = []
    color_map = {
        "Work": "#1f77b4",
        "Meeting": "#ff7f0e",
        "Out of Office": "#d62728",
        "On-Call": "#2ca02c",
    }

    for _, row in df.iterrows():
        calendar_events.append(
            {
                "title": f"[{row['event_type']}] {row['event_title']} - {row['user_email'].split('@')[0]}",
                "start": row["start_time"].isoformat(),
                "end": row["end_time"].isoformat(),
                "backgroundColor": color_map.get(row["event_type"], "#333"),
                "borderColor": color_map.get(row["event_type"], "#333"),
                "allDay": False,
            }
        )

    # Calendar options
    calendar_options = {
        "initialDate": st.session_state.view_date.isoformat(),
        "headerToolbar": {"left": "", "center": "title", "right": ""},
    }

    if view_type == "Week":
        calendar_options["initialView"] = "timeGridWeek"
        calendar_options["slotMinTime"] = "06:00:00"
        calendar_options["slotMaxTime"] = "22:00:00"
        calendar_options["allDaySlot"] = False
    else:
        calendar_options["initialView"] = "dayGridMonth"

    # Render Calendar
    st.subheader(f"🗓️ {view_type} View")
    state = calendar(
        events=calendar_events,
        options=calendar_options,
        key=f"calendar-{view_type}-{st.session_state.view_date}",  # Key change triggers refresh
    )

    # Replaced manual list with Calendar view

with st.sidebar:
    st.write("---")
    st.write("### Calendar Legend")
    st.markdown("- 🔵 **Work Shift**")
    st.markdown("- 🟠 **Meeting**")
    st.markdown("- 🟢 **On-Call**")
    st.markdown("- 🔴 **Out of Office**")
