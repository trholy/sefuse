# `streamlit.auth.handlers`

Streamlit-facing façade over the authentication and user-management services. All service instances are constructed once per process via `@lru_cache`.

---

### `is_auth_enabled() -> bool`

Return `True` if authentication is enabled via the `AUTH_ENABLED` environment variable.

**Returns:** `bool` — `True` when auth is active.

---

### `are_session_cookies_enabled() -> bool`

Return `True` if cross-tab session cookies are active (`SESSION_COOKIES_ENABLED=true`).

**Returns:** `bool`

---

### `bootstrap_auth_system() -> None`

Initialise session state and create the admin user on first call per session.

No-op when auth is disabled or the bootstrap flag is already set in `st.session_state`. When session cookies are enabled and no session is active, attempts to restore the session from a browser cookie via `_try_restore_session_from_cookie()`.

**Returns:** `None`

---

### `safe_bootstrap() -> None`

Bootstrap the auth system and stop the page with a user-facing error on failure.

Catches `psycopg2.OperationalError` (DB unreachable), `ConfigurationError` (bad env vars), and any other exception; displays a formatted `st.error` and calls `st.stop()` in each case.

**Returns:** `None`

---

### `login_user(username: str, password: str) -> bool`

Authenticate a user and write them into session state on success.

When `SESSION_COOKIES_ENABLED=true`: creates a database-backed session, sets a browser cookie via JavaScript (which triggers a page reload), and calls `st.stop()`. The caller should **not** call `st.rerun()` afterwards. The cookie carries the `Secure` attribute (HTTPS-only) when `SESSION_COOKIE_SECURE=true`; the default is `false` so the out-of-the-box `http://localhost` deployment can still log in.

When `SESSION_COOKIES_ENABLED=false`: sets session state directly and calls `st.rerun()`. No cookies are written; each browser tab requires a separate login.

Re-raises `AccountDeactivatedError` so the caller can display a specific error message.

**Parameters:**

- `username` (`str`): Raw username from the login form.
- `password` (`str`): Plain-text password attempt.

**Returns:** `bool` — `True` on successful login or when auth is disabled; `False` on invalid credentials.

---

### `logout_user() -> None`

Clear the authenticated user from session state, database session, and cookie.

When `SESSION_COOKIES_ENABLED=true`: deletes the database session, clears the browser cookie via JavaScript (which triggers a page reload), and calls `st.stop()`. The clearing cookie matches the `Secure` attribute used at login (`SESSION_COOKIE_SECURE`). When cookies are disabled: calls `st.rerun()` instead.

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

### `require_page_access(page_title: str, disabled_note: str) -> int`

The whole entry gate for a logged-in-only page, returning the authenticated user's id.

Runs, in order: `safe_bootstrap()`; then, when auth is disabled for the deployment, `st.title(page_title)` plus an `st.info` explaining why the page is empty, and `st.stop()`; otherwise `require_login()`, `render_logout_button()`, and finally the `SESSION_USER_ID` lookup, stopping with a warning when the session carries no id. Used by the Watchlist, Saved Searches and Notification Settings pages, which each repeated these six steps in full.

Deliberately does **not** render the title on the success path: the callers place their own `st.title` at different points — the Saved Searches page renders its alert-matches section above its title — so titling here would reorder a page rather than tidy it.

`disabled_note` completes the sentence "Authentication is disabled. …". It is passed in rather than derived from `page_title` because the subject's number varies ("Watchlist requires", "Saved searches require").

**Parameters:**

- `page_title` (`str`): Heading shown only on the auth-disabled branch.
- `disabled_note` (`str`): Sentence completing the auth-disabled explanation.

**Returns:** `int` — the authenticated user's id. Every other path ends in `st.stop()`, which raises, so callers can treat the result as always present.

---

### `get_unread_notification_count() -> int`

Return the number of unread alert notifications for the current user. Returns 0 if auth is disabled, the user is not authenticated, or the database is unreachable.

**Returns:** `int`

---

### `render_logout_button() -> None`

Render a sidebar logout button, unread notification badge, and username/role caption for authenticated users.

No-op when auth is disabled or no user is logged in. Shows the unread alert count when greater than zero. Calls `logout_user()` when the button is clicked.

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

### `set_user_active(username: str, active: bool) -> None`

Activate or deactivate a non-admin user account.

**Parameters:**

- `username` (`str`): Username of the account to update.
- `active` (`bool`): `True` to activate, `False` to deactivate.

**Returns:** `None`

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

Handles `AccountDeactivatedError`, `AuthenticationError`, `UserAlreadyExistsError`, `UserNotFoundError`, `ValidationError`, `AuthorizationError`, and `ConfigurationError`.

**Parameters:**

- `error` (`Exception`): Exception raised by an auth service method.

**Returns:** `str` — human-readable error message.
