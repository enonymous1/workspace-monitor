import os
import sys
import time

import pandas as pd
import polyline
import requests
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.api_client import api_get, api_post
from utils.ui_helpers import enforce_login, show_common_sidebar

# Auth Check
enforce_login()

def check_route_cache(addr_start, addr_end):
    """Checks the backend database for a cached route."""
    try:
        return api_get(
            "route-cache",
            token=st.session_state.get("auth_token", ""),
            params={"addr_start": addr_start, "addr_end": addr_end},
        )
    except Exception as e:
        st.error(f"Error checking route cache: {e}")
    return None

def save_to_route_cache(addr_start, addr_end, distance, duration, geometry):
    """Saves a newly calculated route to the backend database."""
    try:
        api_post(
            "route-cache",
            {
                "addr_start": addr_start,
                "addr_end": addr_end,
                "distance_miles": distance,
                "duration_minutes": duration,
                "geometry_polyline": geometry,
            },
            token=st.session_state.get("auth_token", ""),
        )
    except Exception as e:
        st.error(f"Error saving route to cache: {e}")

st.set_page_config(
    page_title="Distance Calculator",
    page_icon="🗺️",
    layout="wide",
)

@st.cache_data(ttl=3600)
def get_coordinates(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    # Using a more standard/identifiable User-Agent to avoid 403 blocks
    headers = {
        "User-Agent": "ss-workspace-monitor/2.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        else:
            st.error(f"Could not find coordinates for: \"{address}\"")
            return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"Geocoding request failed for \"{address}\": {e}")
        return None, None

@st.cache_data(ttl=3600)
def get_driving_distance(coords1, coords2):
    lon1, lat1 = coords1[1], coords1[0]
    lon2, lat2 = coords2[1], coords2[0]

    # Requesting 'full' overview to get geometry for mapping
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    params = {'overview': 'full'} # Default is polyline format

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('code') == 'Ok':
            route = data['routes'][0]
            distance_meters = route['distance']
            duration_seconds = route['duration']
            distance_miles = distance_meters * 0.000621371
            duration_minutes = duration_seconds / 60
            geometry_polyline = route['geometry']
            return distance_miles, duration_minutes, geometry_polyline
        else:
            st.error(f"Routing failed: {data.get('message', 'Unknown OSRM error')}")
            return None, None, None
    except requests.exceptions.RequestException as e:
        st.error(f"Routing request failed: {e}")
        return None, None, None

if not st.session_state.get("is_logged_in", False):
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.warning("Please log in first to access this page.")
    st.stop()

st.session_state.current_page_key = "distance"
show_common_sidebar()

st.title("🗺️ Live Driving Distance Calculator")
st.info("This tool uses the free Nominatim and OSRM APIs. Results are cached locally.")

# --- Address Inputs ---
col1, col2 = st.columns(2)
address1 = col1.text_input("Start Address", value="Stafford Courthouse, VA")
address2 = col2.text_input("End Address", value="Culpeper Courthouse, VA")

# --- Logic and Data Gathering ---
route_df = None
distance = None
duration = None
methodology = ""

if st.button("Calculate Driving Distance"):
    if not address1 or not address2:
        st.warning("Please enter both addresses.")
    else:
        # Check database cache first
        cached_route = check_route_cache(address1, address2)

        if cached_route:
            distance = cached_route['distance_miles']
            duration = cached_route['duration_minutes']
            geometry = cached_route['geometry_polyline']

            # Decode for map
            route_coords = polyline.decode(geometry)
            route_df = pd.DataFrame(route_coords, columns=['lat', 'lon'])
            methodology = "Retrieved from Route Cache Database"
        else:
            with st.spinner("Geocoding and calculating..."):
                coords1 = get_coordinates(address1)
                time.sleep(1) # Small delay for Nominatim API
                coords2 = get_coordinates(address2)

                if coords1[0] and coords2[0]:
                    distance, duration, geometry = get_driving_distance(coords1, coords2)

                    if distance and duration:
                        # Save to database cache
                        save_to_route_cache(address1, address2, distance, duration, geometry)

                        # Decode for map
                        route_coords = polyline.decode(geometry)
                        route_df = pd.DataFrame(route_coords, columns=['lat', 'lon'])
                        methodology = f"Calculated via OSRM (Start: {coords1[0]}, {coords1[1]} | End: {coords2[0]}, {coords2[1]})"

# --- Unified Map Display ---
if route_df is not None:
    st.success(f"Route Found! Distance: {distance:.2f} miles, Duration: {duration:.2f} minutes")
    st.map(route_df, zoom=10)
    with st.expander("🔬 Route Details & Methodology"):
        st.write(f"**{methodology}**")
        st.write(f"Address 1: `{address1}`")
        st.write(f"Address 2: `{address2}`")
else:
    # Default Overview Map when no route is calculated
    va_hub_data = pd.DataFrame({
        'lat': [38.4232, 38.4732, 38.0293],
        'lon': [-77.4080, -77.9961, -78.4767],
        'name': ['Stafford Hub', 'Culpeper Branch', 'Charlottesville HQ']
    })
    st.map(va_hub_data, zoom=8)

