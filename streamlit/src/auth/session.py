import streamlit as st

from .constants import (
    ROLE_ADMIN,
    SESSION_AUTHENTICATED,
    SESSION_BOOTSTRAPPED,
    SESSION_ROLE,
    SESSION_USERNAME,
)
from .models import UserRecord


def initialize_session_state() -> None:
    st.session_state.setdefault(SESSION_AUTHENTICATED, False)
    st.session_state.setdefault(SESSION_USERNAME, None)
    st.session_state.setdefault(SESSION_ROLE, None)
    st.session_state.setdefault(SESSION_BOOTSTRAPPED, False)


def set_authenticated_user(user: UserRecord) -> None:
    st.session_state[SESSION_AUTHENTICATED] = True
    st.session_state[SESSION_USERNAME] = user.username
    st.session_state[SESSION_ROLE] = user.role


def clear_authenticated_user() -> None:
    st.session_state[SESSION_AUTHENTICATED] = False
    st.session_state[SESSION_USERNAME] = None
    st.session_state[SESSION_ROLE] = None


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_AUTHENTICATED, False))


def is_admin() -> bool:
    return st.session_state.get(SESSION_ROLE) == ROLE_ADMIN


def get_bootstrap_flag() -> bool:
    return bool(st.session_state.get(SESSION_BOOTSTRAPPED, False))


def set_bootstrap_flag(value: bool) -> None:
    st.session_state[SESSION_BOOTSTRAPPED] = value

