# `streamlit.auth.handlers`

Streamlit-facing façade over the authentication and user-management services. All service instances are constructed once per process via `@lru_cache`.

---

### `is_auth_enabled() -> bool`

Return `True` if authentication is enabled via the `AUTH_ENABLED` environment variable.

**Returns:** `bool` — `True` when auth is active.

---

### `bootstrap_auth_system() -> None`

Initialise session state and create the admin user on first call per session.

No-op when auth is disabled or the bootstrap flag is already set in `st.session_state`.

**Returns:** `None`

---

### `safe_bootstrap() -> None`

Bootstrap the auth system and stop the page with a user-facing error on failure.

Catches `psycopg2.OperationalError` (DB unreachable), `ConfigurationError` (bad env vars), and any other exception; displays a formatted `st.error` and calls `st.stop()` in each case.

**Returns:** `None`

---

### `login_user(username: str, password: str) -> bool`

Authenticate a user and write them into session state on success.

**Parameters:**

- `username` (`str`): Raw username from the login form.
- `password` (`str`): Plain-text password attempt.

**Returns:** `bool` — `True` on successful login or when auth is disabled; `False` on invalid credentials.

---

### `logout_user() -> None`

Clear the authenticated user from session state (logout).

**Returns:** `None`

---

### `is_authenticated() -> bool`

Return `True` if the current session has an authenticated user (or auth is disabled).

**Returns:** `bool`

---

### `is_admin() -> bool`

Return `True` if the current session user has the admin role (or auth is disabled).

**Returns:** `bool`

---

### `require_login() -> None`

Stop the Streamlit page with a login prompt if the user is not authenticated.

Shows a title and info message then calls `st.stop()`. No-op when auth is disabled or the user is already logged in.

**Returns:** `None`

---

### `require_admin() -> None`

Stop the Streamlit page with an error if the user is not an admin.

Calls `require_login()` first, then checks the admin role. Shows `st.error` and calls `st.stop()` if the user lacks admin access. No-op when auth is disabled.

**Returns:** `None`

---

### `render_logout_button() -> None`

Render a sidebar logout button and username/role caption for authenticated users.

No-op when auth is disabled or no user is logged in. Calls `logout_user()` and `st.rerun()` when the button is clicked.

**Returns:** `None`

---

### `list_users() -> list[dict]`

Return all users as plain dicts for display in the admin page.

**Returns:** `list[dict]` — each dict contains `id`, `username`, `role`, `is_active`, `created_at`, `updated_at`.

---

### `create_user(username: str, password: str, role: str = "user") -> None`

Create a new user via the authentication service.

**Parameters:**

- `username` (`str`): Desired username.
- `password` (`str`): Plain-text password.
- `role` (`str`, default `"user"`): Assigned role (`"user"` or `"admin"`).

**Returns:** `None`

**Raises:** `ValidationError`, `UserAlreadyExistsError` — propagated from `AuthenticationService.create_user`.

---

### `update_password(username: str, new_password: str) -> None`

Change a user's password via the user management service.

**Parameters:**

- `username` (`str`): Username of the account to update.
- `new_password` (`str`): New plain-text password.

**Returns:** `None`

**Raises:** `ValidationError`, `UserNotFoundError` — propagated from `UserManagementService.update_password`.

---

### `delete_user(username: str) -> None`

Delete a non-admin user via the user management service.

**Parameters:**

- `username` (`str`): Username of the account to delete.

**Returns:** `None`

**Raises:** `UserNotFoundError`, `AuthorizationError` — propagated from `UserManagementService.delete_user`.

---

### `to_user_message(error: Exception) -> str`

Convert a domain auth exception to a user-facing string suitable for `st.error(...)`.

**Parameters:**

- `error` (`Exception`): Exception raised by an auth service method.

**Returns:** `str` — human-readable error message.
