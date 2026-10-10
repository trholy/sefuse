import streamlit as st

from auth.handlers import (
    get_user_repository,
    get_user_gotify_token,
    gotify_push_enabled,
    require_page_access,
)

user_id = require_page_access(
    "Notification Settings", "Notification settings require authentication."
)

st.title("Notification Settings")

if not gotify_push_enabled():
    st.info(
        "Push notifications are disabled on this instance. Alert matches will "
        "still appear on the **Saved Searches** page."
    )
    st.stop()

# Imported after the enabled check so a misconfigured deployment cannot break
# the page before it has had the chance to explain itself.
from shared.gotify import GotifyClient, verify_token  # noqa: E402
from shared.gotify_config import get_gotify_config  # noqa: E402

config = get_gotify_config()
current_token = get_user_gotify_token(user_id)

st.markdown(
    f"""
Alerts are pushed through this instance's Gotify server at
**{config.base_url}**. Each user sends to their own channel, so you need your
own application token:

1. Sign in to [{config.base_url}]({config.base_url}).
2. Go to **Apps** and create an application (for example, *SeFuSe*).
3. Copy the token it shows you and paste it below.
"""
)

if current_token:
    st.success("An app token is configured for your account.")
else:
    st.warning("No app token configured — you will not receive push notifications.")

token_input = st.text_input(
    "Gotify app token",
    value="",
    type="password",
    help=(
        "Leave blank to keep your current token. Saving verifies the token by "
        "sending a test notification."
    ),
    placeholder="••••••••••••••••" if current_token else "",
)

col_save, col_test, col_clear = st.columns(3)

with col_save:
    if st.button("Save token", type="primary"):
        candidate = token_input.strip()
        if not candidate:
            st.error("Enter a token to save.")
        else:
            # Verify before storing so a typo is caught here rather than
            # silently producing no notifications for weeks.
            ok, reason = verify_token(config.base_url, candidate)
            if ok:
                try:
                    get_user_repository().update_gotify_token(user_id, candidate)
                    st.success(f"{reason} Your token has been saved.")
                    st.rerun()
                except Exception:
                    st.error("Could not save your token. Please try again.")
            else:
                st.error(reason)

with col_test:
    if st.button("Send test notification", disabled=not current_token):
        sent = GotifyClient(current_token).send(
            "SeFuSe",
            'funding alert — "[Example funding program](https://example.org)" '
            'from EU matches your search "Test search"',
        )
        if sent:
            st.success("Test notification sent.")
        else:
            st.error(
                "Could not send. Your token may have been revoked on the "
                "Gotify server — save a new one above."
            )

with col_clear:
    if st.button("Remove token", disabled=not current_token):
        try:
            get_user_repository().update_gotify_token(user_id, "")
            st.success("Token removed. Push notifications are now off.")
            st.rerun()
        except Exception:
            st.error("Could not remove your token. Please try again.")
