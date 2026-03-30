import streamlit as st
from psycopg2 import OperationalError

from utils.auth import (
    bootstrap_auth_system,
    is_authenticated,
    is_auth_enabled,
    login_user,
    render_logout_button,
)

st.set_page_config(
    page_title="SeFuSe",
    layout="centered",
    page_icon="favicon.jpg"
)


def render_login_screen() -> None:
    st.title("SeFuSe Login")
    st.write("Please sign in with your username and password.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if login_user(username, password):
            st.rerun()
        st.error("Invalid username or password.")


def render_home_content() -> None:
    st.title("Semantic Funding Search (SeFuSe)")
    description_text = (
        "Use **SeFuSE** to semantically search two funding sources:\n"
        "- **[Federal Funding Database:](https://www.foerderdatenbank.de/FDB/DE/Foerderprogramme/foerderprogramme.html)** Search German federal funding programs with optional filters (funding location, funding type, eligible applicants, funding area).\n"
        "- **[EU Funding Programs:](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home)** Search EU calls, with EU-specific fields such as description, deadline date, and publication date.\n\n"
        "On both pages, enter your project idea in natural language to get the most relevant funding calls ranked by similarity."
    )
    st.write(description_text)

    st.space(size="small")
    info_text = (
        "**Development Background:** This tool was developed in response to an urgent need and is now being improved based on community feedback. The aim of this initiative is to simplify and streamline the search for suitable funding programs for interested users, such as staff in transfer centers and researchers.\n\n"
        "**Data Processing:** When the tool is operated on local infrastructure, no data is stored long-term. No data leaves the local system, and there is no access to external APIs or any other form of external data transfer.\n\n "
    )
    st.write(info_text)

    st.space(size="large")
    about_text = (
        "Source code available on [GitHub](https://github.com/trholy/sefuse)."
        " Read the [Docs](https://to82lod.gitpages.uni-jena.de/sefuse/)."
        " Licensed under [BSD-3-Clause](https://github.com/trholy/sefuse/blob/main/LICENSE)."
    )
    st.write(about_text)


try:
    bootstrap_auth_system()
except OperationalError:
    st.error(
        "Could not connect to the authentication database."
        " Please check Docker Compose and DB credentials."
    )
    st.stop()
except Exception as error:
    st.error(f"Authentication initialization failed: {error}")
    st.stop()

if is_auth_enabled() and not is_authenticated():
    render_login_screen()
    st.stop()

render_logout_button()
render_home_content()
