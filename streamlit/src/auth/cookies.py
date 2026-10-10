"""Browser cookie management for cross-tab session persistence.

Reads cookies via ``st.context.cookies`` (read-only, available since
Streamlit 1.37). Sets/clears cookies by injecting a zero-height
``<script>`` tag through ``st.components.v1.html()``.
"""

import logging

import streamlit as st
import streamlit.components.v1 as components

from .constants import SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)

_COOKIE_SET_FLAG = "_cookie_js_injected"


def read_session_cookie() -> str | None:
    """Read the session token from the browser cookie.

    Returns:
        Token string, or ``None`` if no session cookie is present.
    """
    try:
        return st.context.cookies.get(SESSION_COOKIE_NAME)
    except Exception:
        logger.debug("st.context.cookies not available")
        return None


def set_session_cookie(
    token: str, max_age_seconds: int, *, reload: bool = False, secure: bool = False
) -> None:
    """Set the session cookie in the browser via JavaScript injection.

    Guarded to run at most once per Streamlit render cycle to avoid
    multiple invisible iframes.

    Args:
        token: Session token to store.
        max_age_seconds: Cookie lifetime in seconds.
        reload: If True, the JS also reloads the parent page after
            setting the cookie so that ``st.context.cookies`` picks
            it up on the next server round-trip.
        secure: If True, append the ``Secure`` attribute so the cookie is
            only sent over HTTPS. Defaults to False so the out-of-the-box
            ``http://localhost`` deployment still works; enable via
            ``SESSION_COOKIE_SECURE`` when serving over TLS.
    """
    if st.session_state.get(_COOKIE_SET_FLAG):
        return
    reload_js = "window.parent.location.reload();" if reload else ""
    secure_attr = "; Secure" if secure else ""
    js = (
        "<script>"
        f'document.cookie = "{SESSION_COOKIE_NAME}={token};'
        f" path=/; max-age={max_age_seconds}; SameSite=Strict{secure_attr}\";"
        f" {reload_js}"
        "</script>"
    )
    components.html(js, height=0, width=0)
    st.session_state[_COOKIE_SET_FLAG] = True


def clear_session_cookie(*, reload: bool = False, secure: bool = False) -> None:
    """Delete the session cookie by setting it with ``max-age=0``.

    Args:
        reload: If True, reload the parent page after clearing so
            the server sees the cookie is gone on the next request.
        secure: If True, append the ``Secure`` attribute so the deletion
            matches a cookie originally set with ``Secure`` over HTTPS.
    """
    reload_js = "window.parent.location.reload();" if reload else ""
    secure_attr = "; Secure" if secure else ""
    js = (
        "<script>"
        f'document.cookie = "{SESSION_COOKIE_NAME}=;'
        f' path=/; max-age=0; SameSite=Strict{secure_attr}"; {reload_js}'
        "</script>"
    )
    components.html(js, height=0, width=0)
    st.session_state.pop(_COOKIE_SET_FLAG, None)
