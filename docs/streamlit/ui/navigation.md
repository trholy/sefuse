# `streamlit.ui.navigation`

Builds the sidebar page list for `st.navigation`.

The app is routed from `Home.py` through `st.navigation` rather than through Streamlit's automatic page discovery, so that the page list can depend on who is logged in.

---

## Why the directory is called `app_pages/`

The page scripts live in `streamlit/src/app_pages/` (`/app/app_pages/` in the container), **not** `pages/`. The name is load bearing.

Streamlit switches to its legacy multi-page mode whenever a directory called `pages` sits next to the entry-point script (`PagesManager.uses_pages_directory`). In that mode Streamlit builds the sidebar itself from every `*.py` file it finds there and runs the selected page — so `Home.py` never executes for any page but the default, and the admin link reappears for every user regardless of what this module returns.

Renaming the directory back to `pages/` silently reverts the admin-only navigation. `tests/test_streamlit/test_navigation.py` asserts the `app_pages/` prefix to catch that.

---

## Module constants

| Constant | Value |
|---|---|
| `FEDERAL_PAGE` | `"app_pages/1_Federal_Funding_Database.py"` |
| `EU_PAGE` | `"app_pages/2_EU_Funding_Programs.py"` |
| `ADMIN_PAGE` | `"app_pages/3_Admin_User_Management.py"` |
| `WATCHLIST_PAGE` | `"app_pages/4_Watchlist.py"` |
| `SAVED_SEARCHES_PAGE` | `"app_pages/5_Saved_Searches.py"` |
| `HOW_TO_USE_PAGE` | `"app_pages/6_How_to_Use.py"` |
| `NOTIFICATION_SETTINGS_PAGE` | `"app_pages/7_Notification_Settings.py"` |

`5_Saved_Searches.py` imports `FEDERAL_PAGE` and `EU_PAGE` for its `st.switch_page()` "Restore" buttons, so the paths are declared once.

---

### `build_navigation_pages(home_page: Callable[[], None]) -> list`

Return the pages this session may navigate to, in sidebar order.

Admin User Management is included only when `is_admin()` is true, so a normal user is not shown a link to a page they cannot open. This is presentation only — `3_Admin_User_Management.py` still calls `require_admin()`, which remains the actual access check.

Notification Settings is gated the same way, on `gotify_push_enabled()`: there would be nothing to configure when push is off for the deployment, and the page re-checks and explains itself if reached directly. Because `gotify_push_enabled()` returns `False` whenever `ALERTS_ENABLED` is off, switching alerts off removes this page through the gate that was already here — this module needs no separate alerts check. The Saved Searches page is *not* gated: it stays usable for restoring and deleting saved searches, and hides only its own alert sections.

**Parameters:**

- `home_page` (`Callable[[], None]`): Renderer for the default landing page, supplied by `Home.py` where the home content lives.

**Returns:** `list` — `st.Page` objects to hand to `st.navigation`. Home is marked `default=True` with `url_path="home"`.

**Order:** Home, Federal Funding Database, EU Funding Programs, *(Admin User Management)*, Watchlist, Saved Searches, *(Notification Settings)*, How to Use.

---

## Page config

Because only the entry point may call `st.set_page_config` under `st.navigation`, none of the page scripts call it. Browser tab titles come from the `title` argument of each `st.Page`.
