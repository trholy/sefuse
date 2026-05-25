import time
from functools import lru_cache

import streamlit as st

from .config import load_auth_settings
from .constants import (
    ROLE_ADMIN,
    SESSION_AUTHENTICATED,
    SESSION_BOOTSTRAPPED,
    SESSION_LOGIN_TIME,
    SESSION_ROLE,
    SESSION_USERNAME,
)
from .models import UserRecord


@lru_cache(maxsize=1)
def _get_session_timeout_seconds() -> int:
    return load_auth_settings().session_timeout_minutes * 60


def initialize_session_state() -> None:
    """Set default values for all auth-related session state keys if not already present."""
    st.session_state.setdefault(SESSION_AUTHENTICATED, False)
    st.session_state.setdefault(SESSION_USERNAME, None)
    st.session_state.setdefault(SESSION_ROLE, None)
    st.session_state.setdefault(SESSION_BOOTSTRAPPED, False)
    st.session_state.setdefault(SESSION_LOGIN_TIME, None)


def set_authenticated_user(user: UserRecord) -> None:
    """Write a successfully authenticated user into Streamlit session state.

    Args:
        user (UserRecord): Authenticated user record from `AuthenticationService.authenticate`.
    """
    st.session_state[SESSION_AUTHENTICATED] = True
    st.session_state[SESSION_USERNAME] = user.username
    st.session_state[SESSION_ROLE] = user.role
    st.session_state[SESSION_LOGIN_TIME] = time.time()


def clear_authenticated_user() -> None:
    """Clear auth session state keys (logout)."""
    st.session_state[SESSION_AUTHENTICATED] = False
    st.session_state[SESSION_USERNAME] = None
    st.session_state[SESSION_ROLE] = None
    st.session_state[SESSION_LOGIN_TIME] = None


def _is_session_expired() -> bool:
    """Check whether the current session has exceeded the inactivity timeout.

    The timeout is read from `AuthSettings.session_timeout_minutes` (default 30).
    A missing login timestamp is treated as expired.

    Returns:
        bool: True if the session is expired or no login time is recorded.
    """
    login_time = st.session_state.get(SESSION_LOGIN_TIME)
    if login_time is None:
        return True
    return (time.time() - login_time) > _get_session_timeout_seconds()


def is_authenticated() -> bool:
    """Return True if the current session has a logged-in user whose session has not expired.

    Refreshes the activity timestamp on every successful check (sliding window).
    """
    if not st.session_state.get(SESSION_AUTHENTICATED, False):
        return False
    if _is_session_expired():
        clear_authenticated_user()
        return False
    st.session_state[SESSION_LOGIN_TIME] = time.time()
    return True


def is_admin() -> bool:
    """Return True if the current session user has the admin role."""
    return st.session_state.get(SESSION_ROLE) == ROLE_ADMIN


def get_bootstrap_flag() -> bool:
    """Return True if the auth system has already been bootstrapped this session."""
    return bool(st.session_state.get(SESSION_BOOTSTRAPPED, False))


def set_bootstrap_flag(value: bool) -> None:
    """Persist the bootstrap completion flag in session state.

    Args:
        value (bool): True once `bootstrap_auth_system` has completed successfully.
    """
    st.session_state[SESSION_BOOTSTRAPPED] = value

