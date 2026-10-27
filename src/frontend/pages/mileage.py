import os
import sys

import pandas as pd
import streamlit as st

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.api_client import api_get, api_post
from utils.ui_helpers import current_role, enforce_login, fetch_data, show_common_sidebar

st.set_page_config(
    page_title="Mileage Log & Verification",
    page_icon="🚗",
    layout="wide",
)

# Auth Check
enforce_login()

st.session_state.current_page_key = "mileage"
show_common_sidebar()

st.title("🚗 Mileage Log & tracking")

def fetch_mileage(user_email=None):
    try:
        params = {"user_email": user_email} if user_email else None
        return api_get("mileage", token=st.session_state.get("auth_token", ""), params=params)
    except Exception as e:
        st.error(f"Error fetching mileage: {e}")
    return []

def save_mileage(data):
    try:
        api_post("mileage", data, token=st.session_state.get("auth_token", ""))
        return True
    except Exception as e:
        st.error(f"Error saving mileage: {e}")
    return False

# --- UI Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Mileage Log", "➕ Add / Upload", "🛠️ Tools & Apps"])

with tab1:
    st.subheader("Your Recorded Mileage")

    filter_user = None
    if current_role() == "Admin":
        users_data = fetch_data("users") or []
        full_user_list = [u["email"] for u in users_data]
        filter_user = st.selectbox("View logs for:", ["All"] + full_user_list, key="mileage_user_filter")
        if filter_user == "All":
            filter_user = None

    mileage_data = fetch_mileage(filter_user)
    if mileage_data:
        df = pd.DataFrame(mileage_data)

        # Summary metrics
        total_miles = df['miles'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Miles", f"{total_miles:.1f}")
        col2.metric("Entries", len(df))
        col3.metric("Verified", len(df[df['status'] == 'verified']))

        st.dataframe(
            df[['date', 'user_email', 'start_location', 'end_location', 'miles', 'purpose', 'status']],
            column_config={
                "miles": st.column_config.NumberColumn("Miles", format="%.1f"),
                "status": st.column_config.SelectboxColumn("Status", options=["pending", "verified", "rejected"])
            }
        )

        # Export option
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Export Mileage to CSV",
            csv,
            "mileage_export.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("No mileage logs found.")

with tab2:
    st.subheader("Add New Mileage Entry")

    col_a, col_b = st.columns(2)

    with col_a:
        st.write("Manual Entry")
        with st.form("mileage_form"):
            m_date = st.date_input("Date")
            m_start = st.text_input("Start Location")
            m_end = st.text_input("End Location")
            m_miles = st.number_input("Total Miles", min_value=0.1, step=0.1)
            m_purpose = st.text_input("Purpose")

            if st.form_submit_button("Save Entry"):
                new_entry = {
                    "user_email": st.session_state.user_email,
                    "date": str(m_date),
                    "start_location": m_start,
                    "end_location": m_end,
                    "miles": m_miles,
                    "purpose": m_purpose
                }
                if save_mileage(new_entry):
                    st.success("Mileage entry saved successfully!")
                    st.rerun()

    with col_b:
        st.write("Upload from CSV / Excel")
        st.info("Format: date, start_location, end_location, miles, purpose")
        uploaded_file = st.file_uploader("Upload Mileage Log", type=['csv', 'xlsx'])

        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    upload_df = pd.read_csv(uploaded_file)
                else:
                    upload_df = pd.read_excel(uploaded_file)

                st.write("Preview of data to upload:")
                st.dataframe(upload_df.head())

                if st.button("Confirm Bulk Upload"):
                    success_count = 0
                    for _, row in upload_df.iterrows():
                        entry = {
                            "user_email": st.session_state.user_email,
                            "date": str(row['date']),
                            "start_location": str(row['start_location']),
                            "end_location": str(row['end_location']),
                            "miles": float(row['miles']),
                            "purpose": str(row['purpose'])
                        }
                        if save_mileage(entry):
                            success_count += 1
                    st.success(f"Successfully uploaded {success_count} entries!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error processing file: {e}")

with tab3:
    st.subheader("Recommended Tracking Apps & verification")

    st.markdown("""
    ### 📱 Recommended Apps for Mileage Tracking
    To make your life easier, we recommend using these free/low-cost apps that capture geolocation automatically. You can export their data and upload it here:

    1. **Stride** (Free) - Great for automatic tracking and IRS-compliant reports.
    2. **MileIQ** - High accuracy, easy swipe-to-classify interface.
    3. **Hurdlr** - Excellent for freelancers and business owners.

    ### 🛡️ verification Methodology
    To verify mileage logs, we cross-reference:
    - **Distance Calculator**: We use OSRM to check if the 'Miles' claimed match the actual driving route between start/end points.
    - **Schedule Sync**: We check if meeting events in your Workspace Calendar correspond to your mileage dates and purposes.
    - **Geolocation**: Clock-in data from the Workspace app can be used to confirm your presence at start/end locations.
    """)

    if st.button("Run verification Check (Audit)"):
        st.warning("Feature in progress: This will cross-reference your logs with the OSRM Routing API.")
