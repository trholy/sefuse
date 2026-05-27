# `streamlit.Home`

Entry-point module for the Streamlit home page and login screen.

Configures the Streamlit page (`page_title="SeFuSe"`, centered layout), runs `safe_bootstrap()` on every load, shows the login form when auth is enabled and no authenticated session is present, and renders the authenticated home content otherwise.

---

### `_render_login_form() -> None`

Render the username/password login form and attempt login on submit.

Displays a Streamlit form with username and password fields. On submission calls `login_user()`; reruns the page on success or shows `st.error` on failure.

**Returns:** `None`

---

### `render_login_screen() -> None`

Render the full login screen: page title, instruction text, and the login form.

**Returns:** `None`

---

### `render_home_content() -> None`

Render the authenticated home page with the SeFuSe project description, development background, data-processing notes, and links to source code, documentation, and license.

**Returns:** `None`

---

## Module-level execution

| Step | Action |
|---|---|
| 1 | `safe_bootstrap()` — initialises session state and creates the admin user; stops with an error on failure. |
| 2 | If auth is enabled and the user is not authenticated, renders the login screen and calls `st.stop()`. |
| 3 | `render_logout_button()` — shows the sidebar logout button for authenticated users. |
| 4 | `render_home_content()` — renders the main page body. |
