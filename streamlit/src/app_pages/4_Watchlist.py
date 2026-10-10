import streamlit as st

from auth.handlers import get_watchlist_repository, require_page_access
from utils import format_timestamp

user_id = require_page_access("Watchlist", "Watchlist requires authentication.")

st.title("Watchlist")

repo = get_watchlist_repository()
items = repo.list_items(user_id)

if not items:
    st.info(
        "Your watchlist is empty. "
        "Search for funding programs and add them to your watchlist."
    )
    st.stop()

german_items = [i for i in items if i.collection_type == "german"]
eu_items = [i for i in items if i.collection_type == "eu"]

for label, group in [
    ("Federal Funding", german_items),
    ("EU Funding", eu_items),
]:
    if not group:
        continue
    st.subheader(label)
    for item in group:
        col1, col2 = st.columns([5, 1])
        with col1:
            if item.project_website:
                st.markdown(
                    f"[{item.project_title or 'Untitled'}]"
                    f"({item.project_website})"
                )
            else:
                st.write(item.project_title or "Untitled")
            st.caption(f"Added {format_timestamp(item.added_at)}")
        with col2:
            if st.button("Remove", key=f"rm_wl_{item.id}"):
                repo.remove(user_id, item.project_id, item.collection_type)
                st.rerun()
