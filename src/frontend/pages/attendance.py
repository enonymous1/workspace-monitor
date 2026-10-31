import os
import sys
import time

import pandas as pd
import requests
import streamlit as st
from streamlit_js_eval import get_geolocation

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.api_client import api_get, api_post
from utils.ui_helpers import current_role, enforce_login, show_common_sidebar

st.set_page_config(
    page_title="Clock-in Attendance Explorer",
    page_icon="🕒",
    layout="wide",
)

# Auth Check
enforce_login()

st.session_state.current_page_key = "attendance"
show_common_sidebar()

st.title("🕒 Workspace Clock-in Attendance")

# --- Geolocation Clock-in/out ---
st.subheader("📍 Mobile Clock-in / Out")
st.caption("Captures high-accuracy GPS coordinates via your browser's location services.")

location = get_geolocation()


def perform_clock_action(action_type, lat, lon, location_name="Mobile Capture"):
    try:
        api_post(
            f"attendance/{action_type}",
            {"latitude": lat, "longitude": lon, "location_name": location_name},
            token=st.session_state.get("auth_token", ""),
        )
        st.success(f"Successfully {action_type.replace('-', ' ')}!")
        time.sleep(1)
        st.rerun()
    except Exception:
        # api_client raises ApiError with a parsed detail; do not
        # show raw exception text, and do not crash on non-JSON
        # error pages (the v2.0 res.json() call did exactly that).
        st.error("Clock action failed. Please try again.")


if location:
    if "error" in location:
        st.error(
            f"📍 Location Access Denied/Failed: {location['error'].get('message', 'Unknown Error')}. Please enable GPS permissions."
        )
    else:
        coords = location["coords"]
        lat, lon = coords["latitude"], coords["longitude"]

        # --- Optimized Reverse Geocoding ---
        # Cache for 1 hour; round coords to 4 decimal places (~11m)
        # to maximize cache hits if the user is standing still
        @st.cache_data(ttl=3600)
        def get_address_from_coords(lat, lon):
            try:
                # Add a timeout to prevent slow API from blocking the sidebar/UI
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
                headers = {"User-Agent": "ss-workspace-monitor/1.0"}
                resp = requests.get(url, headers=headers, timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    addr = data.get("address", {})
                    # Build a friendly string
                    parts = [
                        addr.get("house_number"),
                        addr.get("road"),
                        addr.get("city") or addr.get("town") or addr.get("village"),
                        addr.get("state"),
                        addr.get("postcode"),
                    ]
                    # Filter out None and join
                    full_addr = ", ".join([p for p in parts if p])
                    return full_addr
            except Exception:
                pass
            return "Address preview unavailable"

        readable_address = get_address_from_coords(round(lat, 4), round(lon, 4))

        col_in, col_out, col_info = st.columns([1, 1, 3])
        with col_in:
            if st.button("🚀 Clock In", key="attendance_clock_in_btn", use_container_width=True):
                perform_clock_action("clock-in", lat, lon, readable_address)
        with col_out:
            if st.button("🏁 Clock Out", key="attendance_clock_out_btn", use_container_width=True):
                perform_clock_action("clock-out", lat, lon, readable_address)
        with col_info:
            # Enhanced coordinate + address information display
            # Using inherit and semi-transparent backgrounds to ensure theme compatibility
            st.markdown(
                f"""
            <div style="background-color:rgba(28, 131, 225, 0.15); padding:15px; border-radius:10px; border:1px solid rgba(28, 131, 225, 0.3)">
                <p style="margin:0; font-weight:bold; color:#1C83E1; font-size:1.1em;">📍 Current GPS Lock</p>
                <div style="margin:8px 0;">
                    <code style="font-size:1.15em; color:#1C83E1; background:none; padding:0;">{lat:.6f}, {lon:.6f}</code>
                </div>
                <div style="margin:10px 0; padding:10px; background-color:rgba(255,255,255,0.05); border-radius:8px; border-left: 3px solid #1C83E1;">
                    <span style="font-weight:bold; color:#1C83E1; font-size:0.9em; text-transform:uppercase;">🏠 Address</span><br>
                    <span style="font-size:1.1em; line-height:1.4;">{readable_address}</span>
                </div>
                <p style="margin:10px 0 0 0; font-size:0.85em; opacity:0.8;">
                    <b>Accuracy:</b> ±{coords.get('accuracy', 0):.1f}m |
                    <b>Alt:</b> {f"{coords.get('altitude', 0):.1f}m" if coords.get('altitude') else "N/A"} |
                    <b>Speed:</b> {f"{coords.get('speed', 0) * 2.237:.1f} mph" if coords.get('speed') else "0 mph"}
                </p>
            </div>
            """,
                unsafe_allow_html=True,
            )
else:
    st.warning(
        "⌛ Waiting for GPS/Location lock... If on mobile, ensure Safari/Chrome has location permissions enabled."
    )

st.divider()


def fetch_attendance():
    """Fetches attendance without @st.cache_data to avoid stale 401s."""
    try:
        return api_get("attendance", token=st.session_state.get("auth_token", ""))
    except Exception:
        st.error("Error connecting to backend.")
        return []


# --- Data Presentation ---
attendance_data = fetch_attendance()

if not attendance_data:
    st.write("No attendance records found.")
else:
    df = pd.DataFrame(attendance_data)

    # Pre-process columns for better display
    df["clock_in_time"] = pd.to_datetime(df["clock_in_time"])
    df["clock_out_time"] = pd.to_datetime(df["clock_out_time"])

    # Calculate duration
    df["duration_hrs"] = (df["clock_out_time"] - df["clock_in_time"]).dt.total_seconds() / 3600

    # Handle Role-based UI
    if current_role() == "Admin":
        st.subheader("👥 All Users' Clock-in Data (Admin View)")

        # Admin Filters
        col1, col2 = st.columns([3, 1])

        with col1:
            # User selection filter with search functionality
            users_list = sorted(df["user_email"].unique().tolist())
            selected_user = st.selectbox(
                "🔍 Search & Filter by User Email:",
                ["All Users"] + users_list,
                index=0,
                help="Type to search for a specific user email or select from the dropdown.",
            )

        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button(
                "📇 View Directory/Users",
                help="Go to the Organization Directory to see a full list of contacts and users.",
            ):
                st.switch_page("pages/directory.py")

        if selected_user != "All Users":
            filtered_df = df[df["user_email"] == selected_user]
        else:
            filtered_df = df

        # Map view for all entries
        st.write("🌍 Geolocation Points (Clock-in Locations)")
        st.map(filtered_df[["latitude", "longitude"]], size=20, color="#ff4b4b")

        # Table view
        st.dataframe(
            filtered_df[
                ["user_email", "clock_in_time", "clock_out_time", "duration_hrs", "location_name"]
            ],
            column_config={
                "duration_hrs": st.column_config.NumberColumn("Hours", format="%.2f"),
                "clock_in_time": st.column_config.DatetimeColumn("Clock In"),
                "clock_out_time": st.column_config.DatetimeColumn("Clock Out"),
            },
        )
    else:
        st.subheader("👤 Your Attendance Records")

        # Simple stats
        avg_hrs = df["duration_hrs"].mean()
        st.metric("Average Daily Hours", f"{avg_hrs:.2f}")

        # Map and Data
        col_map, col_table = st.columns([1, 2])

        with col_map:
            st.write("📌 Your Locations")
            st.map(df[["latitude", "longitude"]], zoom=4)

        with col_table:
            st.dataframe(
                df[["clock_in_time", "clock_out_time", "duration_hrs", "location_name"]],
                column_config={
                    "duration_hrs": st.column_config.NumberColumn("Hours", format="%.2f")
                },
            )

st.divider()
with st.expander("🛠️ API Integration Technical Note"):
    st.write(
        "The frontend communicates with `/api/attendance` which enforces role-based security at the backend level."
    )
    st.code("""
# Backend Enforcement Summary (v2):
# The JWT is verified and the user is re-checked in the database;
# privileged roles see all records, Standard users see only their own.
if is_privileged(auth["role"]):
    cursor.execute("SELECT * FROM attendance ORDER BY clock_in_time DESC")
else:
    cursor.execute(
        "SELECT * FROM attendance WHERE user_email = ? ORDER BY clock_in_time DESC",
        (auth["email"],),
    )
    """)
