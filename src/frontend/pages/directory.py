import os
import sys

import pandas as pd
import streamlit as st

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.api_client import api_delete, api_get, api_post
from utils.ui_helpers import current_role, enforce_login, show_common_sidebar

st.set_page_config(
    page_title="Directory & Contacts",
    page_icon="📇",
    layout="wide",
)

# Auth Check
enforce_login()

st.session_state.current_page_key = "directory"
show_common_sidebar()

st.title("📇 Workspace Directory")

def fetch_contacts():
    try:
        return api_get("contacts", token=st.session_state.get("auth_token", ""))
    except Exception as e:
        st.error(f"Error fetching directory: {e}")
    return []

def delete_contact(contact_id):
    try:
        api_delete(f"contacts/{contact_id}", token=st.session_state.get("auth_token", ""))
        return True
    except Exception as e:
        st.error(f"Error deleting contact: {e}")
    return False

def add_contact(data):
    try:
        api_post("contacts", data, token=st.session_state.get("auth_token", ""))
        return True
    except Exception as e:
        st.error(f"Error adding contact: {e}")
    return False

# --- UI Layout ---
tab1, tab2 = st.tabs(["👥 Directory", "🛠️ Manage Contacts"])

with tab1:
    st.subheader("Personal & Workspace Contacts")
    contacts_data = fetch_contacts()

    if contacts_data:
        df = pd.DataFrame(contacts_data)

        # Search & Filter
        search_query = st.text_input("🔍 Search Name, Title or Email", key="directory_search_input")
        if search_query:
            df = df[df.apply(lambda row: search_query.lower() in str(row).lower(), axis=1)]

        category_filter = st.multiselect("Filter by Category", df['category'].unique(), key="directory_category_filter")
        if category_filter:
            df = df[df['category'].isin(category_filter)]

        # Display Contacts in Cards/List
        for _, contact in df.iterrows():
            with st.container():
                col_icon, col_info, col_extra = st.columns([1, 4, 2])

                # Determine icon/color by category
                cat_color = "#1f77b4" if contact['category'] == 'Universal' else \
                           "#2ca02c" if contact['category'] == 'Supervisor' else \
                           "#ff7f0e" if contact['category'] == 'Team' else "#666"

                with col_icon:
                    st.markdown(f'<div style="font-size: 40px; text-align: center; color: {cat_color};">👤</div>', unsafe_allow_html=True)

                with col_info:
                    st.markdown(f"**{contact['full_name']}**")
                    st.write(f"💼 {contact['job_title']}")
                    st.write(f"📧 {contact['email']} | 📞 {contact['phone']}")

                with col_extra:
                    st.markdown(f'<span style="background-color: {cat_color}; border-radius: 12px; padding: 2px 10px; color: white; float: right;">{contact["category"]}</span>', unsafe_allow_html=True)
                    if contact['owner_email'] == 'universal':
                        st.caption("🌐 (Organization Representative)")
                    elif contact['category'] == 'Supervisor':
                        st.caption("📈 (Reporting Hierarchy)")

                st.divider()
    else:
        st.info("No contacts found in your directory.")

with tab2:
    if current_role() == "Admin":
        st.subheader("🛠️ Organization Directory Management")
        st.info("As an Admin, you can add Universal contacts (visible to all) or assign contacts to specific individuals.")

        with st.expander("➕ Add New Contact Entry"):
            with st.form("add_contact_form"):
                o_type = st.radio("Contact Availability", ["Universal (Organization Wide)", "Individual User Target"], horizontal=True)
                target_email = "universal"
                if o_type == "Individual User Target":
                    target_email = st.text_input("Target User Email (Owner)", value="")

                c1, c2 = st.columns(2)
                f_name = c1.text_input("Full Name")
                j_title = c2.text_input("Job Title")
                e_mail = c1.text_input("Contact Email")
                p_hone = c2.text_input("Contact Phone")
                c_ategory = st.selectbox("Category", ["Universal", "Supervisor", "Team", "Client", "Support"])

                if st.form_submit_button("Create Contact"):
                    if not f_name or not e_mail or not target_email:
                        st.error("Name, Email and Owner are required.")
                    else:
                        payload = {
                            "owner_email": target_email,
                            "full_name": f_name,
                            "job_title": j_title,
                            "email": e_mail,
                            "phone": p_hone,
                            "category": c_ategory
                        }
                        if add_contact(payload):
                            st.success("Contact created!")
                            st.rerun()

        # Delete management list for admins (shows all)
        st.write("---")
        st.write("### Review & Clean Up Directory")
        all_contacts = fetch_contacts()
        if all_contacts:
            del_df = pd.DataFrame(all_contacts)
            st.dataframe(del_df[['id', 'full_name', 'owner_email', 'category']])
            cid_to_del = st.number_input("Enter Contact ID to DELETE", min_value=1, step=1)
            if st.button("🗑️ Delete Contact Permanently", type="primary"):
                if delete_contact(cid_to_del):
                    st.success("Deleted!")
                    st.rerun()
    else:
        st.subheader("🔒 Management Restricted")
        st.warning("Only Administrators can modify universal or cross-user contacts.")
        st.info("Contact your IT administrator to request additions to the universal directory.")

with st.sidebar:
    st.write("---")
    st.write("### Contact Legend")
    st.markdown("- 🌐 **Universal**: Visible to everyone")
    st.markdown("- 📈 **Supervisor**: Specifically assigned to you")
    st.markdown("- 👥 **Team**: Members of your immediate group")
