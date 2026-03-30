import streamlit as st
from psycopg2 import OperationalError

from ui import EuFundingSearchPage
from utils.auth import (
    bootstrap_auth_system,
    render_logout_button,
    require_login,
)

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

require_login()
page = EuFundingSearchPage()
page.render()
render_logout_button()
