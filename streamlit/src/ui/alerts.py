"""Alert widgets shared between the save-search dialog and the Saved Searches page.

These live here rather than in ``shared/`` because they are Streamlit widgets, and
``shared/`` is imported by FastAPI, which has no Streamlit. What *is* shared with
FastAPI is the level vocabulary itself (``shared.alert_levels``); this module is only
how that vocabulary is presented.
"""

import streamlit as st

from shared.alert_levels import DEFAULT_LEVEL, LEVEL_LABELS, LEVELS

#: Explanation shown on every alert-level control. It deliberately describes the rule
#: in terms of ranking and topicality rather than a score, because the numbers behind
#: the levels are a FastAPI implementation detail that never reaches the UI — a user
#: shown "0.72" would have no way to act on it.
LEVEL_HELP = (
    "You are notified when a new funding program would rank among the top matches "
    "of this search and is clearly on topic. Alerts compare meaning, not exact "
    "keywords."
)


def render_alert_level_slider(
    value: str = DEFAULT_LEVEL,
    *,
    key: str | None = None,
    disabled: bool = False,
) -> str:
    """Render the Broad/Balanced/Strict selector and return the chosen level name.

    Args:
        value (str, default=DEFAULT_LEVEL): Level to preselect. The save dialog has no
            saved level yet and takes the default; the Saved Searches page passes the
            stored one.
        key (str | None, default=None): Streamlit widget key. Needed where several
            sliders coexist on one page, one per saved search.
        disabled (bool, default=False): Greys the slider out while still showing it,
            so the choice stays visible when alerts are switched off for the search.

    Returns:
        str: The selected level name, as stored in ``saved_searches.alert_level``.
    """
    return st.select_slider(
        "Match level",
        options=list(LEVELS),
        value=value,
        format_func=LEVEL_LABELS.get,
        key=key,
        disabled=disabled,
        help=LEVEL_HELP,
    )
