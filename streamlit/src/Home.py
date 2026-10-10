import streamlit as st

from auth.exceptions import AccountDeactivatedError, AccountLockedError
from auth.handlers import (
    are_session_cookies_enabled,
    safe_bootstrap,
    is_authenticated,
    is_auth_enabled,
    login_user,
    render_logout_button,
    to_user_message,
)
from auth.session import consume_session_expired
from ui import build_navigation_pages

st.set_page_config(
    page_title="SeFuSe",
    layout="centered",
    page_icon="favicon.jpg"
)


def _render_login_form() -> None:
    """Render the username/password login form and attempt login on submit."""
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if not submitted:
        return

    try:
        if login_user(username, password):
            return
    except (AccountDeactivatedError, AccountLockedError) as error:
        st.error(to_user_message(error))
        return
    st.error("Invalid username or password.")


_COOKIE_NOTICE_SEEN = "_cookie_notice_seen"


@st.dialog("Cookie Notice")
def _cookie_notice_dialog() -> None:
    """Show a one-time popup explaining the session cookie."""
    st.write(
        "This application uses a single **strictly necessary cookie** "
        "(`sefuse_session`) to keep you logged in across browser tabs."
    )
    st.write(
        "It contains a random session token — **no tracking or analytics data**. "
        "The cookie is deleted when you log out or after the configured "
        "session timeout."
    )
    if st.button("OK", use_container_width=True):
        st.session_state[_COOKIE_NOTICE_SEEN] = True
        st.rerun()


def render_login_screen() -> None:
    """Render the full login screen with title, description, and login form.

    When the previous session ended by hitting ``SESSION_TIMEOUT_MINUTES`` rather
    than by an explicit logout, explains that once before the form.
    """
    st.title("SeFuSe Login")
    if consume_session_expired():
        st.warning("Your session expired due to inactivity. Please log in again.")
    st.write("Please sign in with your username and password.")
    _render_login_form()

    if are_session_cookies_enabled() and not st.session_state.get(_COOKIE_NOTICE_SEEN):
        _cookie_notice_dialog()


def render_home_content() -> None:
    """Render the authenticated home page with app description and navigation hints."""
    render_logout_button()
    st.title("Semantic Funding Search (SeFuSe)")
    description_text = (
        "Use **SeFuSe** to semantically search two funding sources:\n"
        "- **[Federal Funding Database:](https://www.foerderdatenbank.de/FDB/DE/Foerderprogramme/foerderprogramme.html)** Search German federal funding programs with optional filters (funding location, funding type, eligible applicants, funding area).\n"
        "- **[EU Funding Programs:](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home)** Search EU calls, with EU-specific fields such as description, deadline date, and publication date.\n\n"
        "On both pages, enter your project idea in natural language to get the most relevant funding calls ranked by similarity."
    )
    st.write(description_text)

    st.markdown("")
    info_text = (
        "**Development Background:** This tool was developed in response to an urgent need and is now being improved based on community feedback. The aim of this initiative is to simplify and streamline the search for suitable funding programs for interested users, such as staff in transfer centers and researchers.\n\n"
        "**Data Processing:** When the tool is operated on local infrastructure, no data is stored long-term. No data leaves the local system, and there is no access to external APIs or any other form of external user data transfer.\n\n"
        "**Acknowledgements:** This project builds upon the data collected by **jstet**, creator of the **[fdb-scraper](https://github.com/CorrelAid/fdb_scraper)** project.\n\n "
    )
    st.write(info_text)

    st.divider()
    about_text = (
        "Source code available on [GitHub](https://github.com/trholy/sefuse)."
        " Read the [Docs](https://to82lod.gitpages.uni-jena.de/sefuse/)."
        " Licensed under [BSD-3-Clause](https://github.com/trholy/sefuse/blob/main/LICENSE)."
    )
    st.write(about_text)


safe_bootstrap()

if is_auth_enabled() and not is_authenticated():
    render_login_screen()
    st.stop()

st.navigation(build_navigation_pages(render_home_content)).run()
