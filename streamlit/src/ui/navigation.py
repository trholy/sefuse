"""Sidebar navigation for the Streamlit app.

The app is routed through ``st.navigation`` from ``Home.py`` rather than through
Streamlit's automatic page discovery, so that the page list can depend on who is
logged in.

The page scripts live in ``app_pages/``, **not** ``pages/``. That name is load
bearing: Streamlit switches to its legacy multi-page mode whenever a directory
called ``pages`` sits next to the entrypoint, and that mode builds the sidebar from
every file it finds there — which would put the admin link back in front of every
user regardless of what this module returns.
"""

from typing import Callable

import streamlit as st

from auth.handlers import gotify_push_enabled, is_admin

# Page script paths, in sidebar order. ``ADMIN_PAGE`` is spliced in at its numeric
# position for admins only.
FEDERAL_PAGE = "app_pages/1_Federal_Funding_Database.py"
EU_PAGE = "app_pages/2_EU_Funding_Programs.py"
ADMIN_PAGE = "app_pages/3_Admin_User_Management.py"
WATCHLIST_PAGE = "app_pages/4_Watchlist.py"
SAVED_SEARCHES_PAGE = "app_pages/5_Saved_Searches.py"
HOW_TO_USE_PAGE = "app_pages/6_How_to_Use.py"
NOTIFICATION_SETTINGS_PAGE = "app_pages/7_Notification_Settings.py"


def build_navigation_pages(home_page: Callable[[], None]) -> list:
    """Return the pages this session may navigate to, in sidebar order.

    Admin User Management is included only for admins, so a normal user is not shown
    a link to a page they cannot open. This is presentation only: the page itself
    still calls ``require_admin()``, which remains the actual access check.

    Notification Settings is hidden the same way when Gotify push is switched off
    for the deployment, since there would be nothing to configure. The page also
    checks for itself and explains the situation if reached directly.

    Args:
        home_page (Callable[[], None]): Renderer for the default landing page,
            supplied by ``Home.py`` where the home content lives.

    Returns:
        list: ``st.Page`` objects to hand to ``st.navigation``.
    """
    pages = [
        st.Page(home_page, title="Home", url_path="home", default=True),
        st.Page(FEDERAL_PAGE, title="Federal Funding Database"),
        st.Page(EU_PAGE, title="EU Funding Programs"),
    ]
    if is_admin():
        pages.append(st.Page(ADMIN_PAGE, title="Admin User Management"))
    pages.append(st.Page(WATCHLIST_PAGE, title="Watchlist"))
    pages.append(st.Page(SAVED_SEARCHES_PAGE, title="Saved Searches"))
    if gotify_push_enabled():
        pages.append(
            st.Page(NOTIFICATION_SETTINGS_PAGE, title="Notification Settings")
        )
    pages.append(st.Page(HOW_TO_USE_PAGE, title="How to Use"))
    return pages
