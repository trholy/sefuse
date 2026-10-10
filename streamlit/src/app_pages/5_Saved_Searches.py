import streamlit as st

from auth.handlers import (
    alerts_enabled,
    get_saved_search_repository,
    get_notification_repository,
    get_user_gotify_token,
    gotify_push_enabled,
    require_page_access,
)
from ui.alerts import render_alert_level_slider
from ui.navigation import EU_PAGE, FEDERAL_PAGE
from ui.search_state import (
    EU_QUERY_KEY,
    FEDERAL_QUERY_KEY,
    RESTORE_KEY,
    RestorePayload,
)
from utils import format_timestamp

_FILTER_LABELS = {
    "funding_type": "Type of funding",
    "funding_area": "Funding area",
    "funding_location": "Funding location",
    "eligible_applicants": "Eligible applicants",
}

user_id = require_page_access(
    "Saved Searches", "Saved searches require authentication."
)

search_repo = get_saved_search_repository()

# Every alert surface on this page is switched off together by ALERTS_ENABLED,
# leaving the saved searches themselves intact — restoring and deleting a search
# has nothing to do with being notified about it.
alerts_on = alerts_enabled()

# Whether this user has a working push channel, used only to decide if the
# "set up push notifications" hint is worth showing next to an enabled alert.
push_configured = (
    alerts_on and gotify_push_enabled() and bool(get_user_gotify_token(user_id))
)

# ── Alert matches ─────────────────────────────────────────────────
# Rendered unconditionally, including its empty state: gating the whole
# section on unread rows made the feature invisible until an alert happened
# to fire, so there was no way to tell it existed.

if alerts_on:
    notif_repo = get_notification_repository()
    notifications = notif_repo.get_recent(user_id)
    unread_count = sum(1 for n in notifications if not n.is_read)

    st.title("Alert Matches")

    if not notifications:
        st.caption(
            "No alert matches yet. Enable alerts on a saved search below and "
            "new matching programs will appear here."
        )
    else:
        col_read, col_clear = st.columns(2)
        with col_read:
            if unread_count and st.button(f"Mark all as read ({unread_count})"):
                notif_repo.mark_all_read(user_id)
                st.rerun()
        with col_clear:
            if st.button("Clear all"):
                notif_repo.delete_all(user_id)
                st.rerun()

        for notif in notifications:
            col1, col2, col3 = st.columns([5, 1, 1])
            with col1:
                # No score is shown. The stored value is a raw cosine, not the
                # relative percentage the search page renders, and the two were
                # being displayed under the same "%" sign on different scales.
                # Alerts are judged by level against the saved query, so a bare
                # number here means nothing to the reader either way.
                title = notif.project_title or "Untitled"
                marker = "**NEW** " if not notif.is_read else ""
                if notif.project_website:
                    st.markdown(f"{marker}[{title}]({notif.project_website})")
                else:
                    st.markdown(f"{marker}{title}")
                st.caption(format_timestamp(notif.created_at))
            with col2:
                if not notif.is_read and st.button("Read", key=f"read_{notif.id}"):
                    notif_repo.mark_read(notif.id, user_id)
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"del_notif_{notif.id}"):
                    notif_repo.delete(notif.id, user_id)
                    st.rerun()

    st.divider()

# ── Saved searches ────────────────────────────────────────────────

st.title("Saved Searches")

searches = search_repo.list_by_user(user_id)

if not searches:
    st.info(
        "No saved searches. "
        "Search for funding programs and save your search."
    )
    st.stop()

for search in searches:
    with st.expander(f"{search.title} ({search.collection_type.upper()})"):
        st.write(f"**Query:** {search.query_text}")
        st.write(f"**Semantic weight:** {search.semantic_weight}")
        st.write(f"**Limit:** {search.search_limit}")
        if search.filters:
            for field, label in _FILTER_LABELS.items():
                values = search.filters.get(field)
                if values:
                    st.write(f"**{label}:** {', '.join(str(v) for v in values)}")
        st.caption(
            f"Created {format_timestamp(search.created_at)}"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Restore", key=f"restore_{search.id}"):
                # One payload for both pages: the target page pops it once and applies
                # the parts it understands, so the EU page no longer has to know that a
                # German filter payload exists in order to avoid leaving it behind.
                st.session_state[RESTORE_KEY] = RestorePayload(
                    filters=search.filters,
                    semantic_weight=search.semantic_weight,
                    limit=search.search_limit,
                )
                german = search.collection_type == "german"
                query_key = FEDERAL_QUERY_KEY if german else EU_QUERY_KEY
                st.session_state[query_key] = search.query_text
                st.switch_page(FEDERAL_PAGE if german else EU_PAGE)
        with col2:
            if st.button("Delete", key=f"delete_{search.id}"):
                search_repo.delete(search.id, user_id)
                st.rerun()

        if not alerts_on:
            continue

        st.markdown("---")
        st.subheader("Alert Settings")

        alert_enabled = st.checkbox(
            "Enable alerts",
            value=search.alert_enabled,
            key=f"alert_on_{search.id}",
        )
        alert_level = render_alert_level_slider(
            search.alert_level, key=f"alert_level_{search.id}"
        )
        if alert_enabled and not push_configured:
            st.caption(
                "Matches will appear above. To also get them pushed to your "
                "phone, add your Gotify app token on the "
                "**Notification Settings** page."
            )

        if st.button("Save Alert Config", key=f"save_alert_{search.id}"):
            search_repo.update_alert_config(
                search_id=search.id,
                user_id=user_id,
                alert_enabled=alert_enabled,
                alert_level=alert_level,
            )
            st.success("Alert configuration saved.")
            st.rerun()

        if search.alert_last_run:
            st.caption(
                f"Last alert check: "
                f"{format_timestamp(search.alert_last_run)}"
            )
