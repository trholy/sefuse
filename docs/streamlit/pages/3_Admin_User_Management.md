# `streamlit.pages.3_Admin_User_Management`

Entry-point script for the admin-only user management page.

Configures the page (`page_title="SeFuSe - Admin User Management"`, centered layout), then executes auth guards and renders the three management forms.

---

### `_render_create_user() -> None`

Render the Create User form and create a new account on submit.

Displays username and password fields. On successful submission calls `create_user()` and triggers a page rerun. On failure calls `to_user_message()` and shows `st.error`.

**Returns:** `None`

---

### `_render_update_password(usernames: list[str]) -> None`

Render the Update Password form and apply the change on submit.

**Parameters:**

- `usernames` (`list[str]`): All current usernames shown in a selectbox for the admin to choose from.

Displays a selectbox and new-password field. On successful submission calls `update_password()` and triggers a page rerun. On failure shows `st.error`.

**Returns:** `None`

---

### `_render_delete_user(deletable_usernames: list[str]) -> None`

Render the Delete User form and permanently remove an account on confirmed submit.

**Parameters:**

- `deletable_usernames` (`list[str]`): Non-admin usernames eligible for deletion. When empty, renders an info message and returns immediately.

Requires the confirmation checkbox to be ticked before deletion proceeds. On successful submission calls `delete_user()` and triggers a page rerun. On failure shows `st.error`.

**Returns:** `None`

---

## Module-level execution

| Step | Action |
|---|---|
| 1 | `safe_bootstrap()` — initialises session state; stops on failure. |
| 2 | If auth is disabled, shows an info message and calls `st.stop()`. |
| 3 | `require_admin()` — stops non-admin users with an error. |
| 4 | `render_logout_button()` — sidebar logout control. |
| 5 | Fetches users via `list_users()` and renders them with `st.table`. |
| 6 | Renders `_render_create_user()`, `_render_update_password()` (when users exist), and `_render_delete_user()`. |
