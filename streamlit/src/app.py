import streamlit as st
import requests
from datetime import datetime
import os

from utils import (
    safe_join,
    read_extracted_filter_options,
    aggregate_chunks,
    apply_filters
)

MODEL = os.getenv('MODEL', 'nomic-embed-text')
FASTAPI_URL = os.getenv('FASTAPI_URL', 'http://fastapi:8000')

# --- Load filter options ---
LOCATION_OPTIONS = read_extracted_filter_options("data/funding_location.txt")
FUNDING_TYPE_OPTIONS = read_extracted_filter_options("data/funding_type.txt")
ELIGIBLE_APPLICANTS_OPTIONS = read_extracted_filter_options("data/eligible_applicants.txt")
FUNDING_AREA_OPTIONS = read_extracted_filter_options("data/funding_area.txt")

# --- Streamlit UI ---
st.set_page_config(page_title="SeFuSe", layout="centered", page_icon="favicon.jpg")
st.title("Semantic Funding Search (SeFuSe)")

query = st.text_area(
    "Enter your project description:",
    height=100,
    max_chars=5000,
    placeholder="Start typing..."
)

st.sidebar.header("Filter Options")
selected_locations = st.sidebar.multiselect(
    "Funding location", LOCATION_OPTIONS
)
selected_funding_type = st.sidebar.multiselect(
    "Type of funding", FUNDING_TYPE_OPTIONS
)
selected_eligible = st.sidebar.multiselect(
    "Eligible applicants", ELIGIBLE_APPLICANTS_OPTIONS
)
selected_funding_area = st.sidebar.multiselect(
    "Funding area", FUNDING_AREA_OPTIONS
)
search_limit = st.sidebar.number_input(
    "Search limit", min_value=5, max_value=50, value=20, step=5
)
drop_na = st.sidebar.checkbox(
    "Drop N/A", value=True
)

if st.button("Search") and query:
    filters = {
        "locations": selected_locations,
        "funding_type": selected_funding_type,
        "eligible": selected_eligible,
        "funding_area": selected_funding_area,
        "drop_na": drop_na
    }

    try:
        resp = requests.post(
            f"{FASTAPI_URL}/v1/search",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": query}],
                "limit": search_limit
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        matches = data.get("matches", [])

        # Aggregate chunks per project
        aggregated_results = aggregate_chunks(matches)
        filtered_results = apply_filters(aggregated_results, filters)

        if filtered_results:
            st.success(f"Found {len(filtered_results)} matching projects")
            for r in filtered_results:
                st.subheader(f"[{r.get('project_title', 'No title')}]({r.get('project_website', '#')})")
                st.write("**Short description:**", r.get("project_short_description", "N/A"))
                st.write("**Full description:**", r.get("project_full_description", "N/A"))

                # Format dates safely
                try:
                    on_website_from = datetime.fromisoformat(r.get("on_website_from"))
                    last_updated = datetime.fromisoformat(r.get("last_updated"))
                    st.write("**On the website since**", on_website_from.strftime("%d %b %Y, %H:%M"))
                    st.write("**Last updated**", last_updated.strftime("%d %b %Y, %H:%M"))
                except Exception:
                    pass

                st.markdown(f"**Type of funding:** {safe_join(r.get('funding_type'))}")
                st.markdown(f"**Target area:** {safe_join(r.get('funding_location'))}")
                st.markdown(f"**Funding area:** {safe_join(r.get('funding_area'))}")
                st.markdown(f"**Eligible applicants:** {safe_join(r.get('eligible_applicants'))}")
                st.write(f"**Score:** {r.get('matching_score', 0) * 100:.1f} %")
        else:
            st.warning("No projects match your selected filters.")

    except Exception as e:
        st.error(f"Error: {e}")
