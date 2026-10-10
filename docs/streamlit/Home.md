# `streamlit.Home`

Entry-point module for the Streamlit app: login screen, home content, and the router.

Configures the Streamlit page (`page_title="SeFuSe"`, centered layout) — the only place in the app that may call `st.set_page_config`, because every other page is run through `st.navigation`. Runs `safe_bootstrap()` on every load, shows the login form when auth is enabled and no authenticated session is present, and otherwise hands off to `st.navigation` with the page list from [`build_navigation_pages()`](ui/navigation.md).

---

### `_render_login_form() -> None`

Render the username/password login form and attempt login on submit.

Displays a Streamlit form with username and password fields. On submission calls `login_user()`; returns on success or shows `st.error` on failure. Catches `AccountDeactivatedError` separately to display a specific deactivation message via `to_user_message()`.

**Returns:** `None`

---

### `_cookie_notice_dialog() -> None`

Show a one-time popup explaining the session cookie. Decorated with `@st.dialog("Cookie Notice")`.

Informs the user that the application uses a single strictly necessary cookie (`sefuse_session`) for cross-tab session persistence. The dialog includes an "OK" button that sets `_cookie_notice_seen` in session state and reruns the page. Only shown when `SESSION_COOKIES_ENABLED=true` and the notice has not yet been dismissed in the current session.

**Returns:** `None`

---

### `render_login_screen() -> None`

Render the full login screen: page title, instruction text, and the login form. When session cookies are enabled and the cookie notice has not been dismissed yet, opens the `_cookie_notice_dialog()` popup.

When the previous session ended by hitting `SESSION_TIMEOUT_MINUTES` rather than by an explicit logout, `consume_session_expired()` returns `True` once and the screen shows "Your session expired due to inactivity." above the form.

**Returns:** `None`

---

### `render_home_content() -> None`

Render the authenticated home page with the SeFuSe project description, development background, data-processing notes, an acknowledgement of CorrelAid's `fdb_scraper` (the source of the German data), and links to source code, documentation, and license. Also renders the sidebar logout button. Passed to `st.navigation` as the default page rather than executed directly.

**Returns:** `None`

---

## Module-level execution

| Step | Action |
|---|---|
| 1 | `safe_bootstrap()` — initialises session state and creates the admin user; stops with an error on failure. |
| 2 | If auth is enabled and the user is not authenticated, renders the login screen and calls `st.stop()`. An unauthenticated visitor therefore sees no navigation at all. |
| 3 | `st.navigation(build_navigation_pages(render_home_content)).run()` — builds the page list for this user (admins additionally get Admin User Management) and runs the selected page. |
