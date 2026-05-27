# `streamlit.auth.services`

Business-logic layer for authentication and user management, sitting between the Streamlit handler façade and the repository data-access layer.

---

## Class `AuthenticationService`

Handles user authentication and initial admin bootstrap.

### `AuthenticationService(repository, password_hasher, settings)`

**Parameters:**

- `repository` (`UserRepositoryProtocol`): Data-access layer for user records.
- `password_hasher` (`PasswordHasher`): bcrypt hasher for creating and verifying hashes.
- `settings` (`AuthSettings`): Application auth configuration.

---

### `bootstrap_admin_user() -> None`

Create the default admin user on first startup if it does not exist yet.

Reads `ADMIN_USERNAME` and `ADMIN_PASSWORD` from settings. No-op when auth is disabled or the admin already exists with the correct role.

**Returns:** `None`

**Raises:** `ConfigurationError` — if `ADMIN_USERNAME` or `ADMIN_PASSWORD` are empty, or if the username already exists with a non-admin role.

---

### `authenticate(username: str, password: str) -> UserRecord`

Verify credentials and return the user record on success.

Always performs a bcrypt check (even for unknown users) to prevent user enumeration via timing attacks.

**Parameters:**

- `username` (`str`): Raw username from the login form.
- `password` (`str`): Plain-text password attempt.

**Returns:** `UserRecord` — authenticated, active user record.

**Raises:** `AuthenticationError` — on invalid credentials, unknown user, or inactive account.

---

### `create_user(username: str, password: str, role: str = "user") -> UserRecord`

Create a new user after validating role, username format, and password strength.

**Parameters:**

- `username` (`str`): Desired username (4–16 alphanumeric/underscore/hyphen characters).
- `password` (`str`): Plain-text password (must meet minimum length from settings).
- `role` (`str`, default `"user"`): Assigned role; must be in `ALLOWED_ROLES`.

**Returns:** `UserRecord` — the newly created user record.

**Raises:**

- `ValidationError` — invalid role, username format, or password that is too short or too long.
- `UserAlreadyExistsError` — if the username is already taken.

---

## Class `UserManagementService`

Admin-facing service for listing users, updating passwords, and deleting accounts.

### `UserManagementService(repository, password_hasher, settings)`

**Parameters:**

- `repository` (`UserRepositoryProtocol`): Data-access layer for user records.
- `password_hasher` (`PasswordHasher`): bcrypt hasher used when updating passwords.
- `settings` (`AuthSettings`): Application auth configuration.

---

### `list_users() -> list[UserSummary]`

Return all users as public summaries (no password hashes), sorted alphabetically by username.

**Returns:** `list[UserSummary]`

---

### `update_password(username: str, new_password: str) -> None`

Change a user's password after validating strength.

**Parameters:**

- `username` (`str`): Username of the account to update.
- `new_password` (`str`): New plain-text password (must meet minimum length from settings).

**Returns:** `None`

**Raises:**

- `ValidationError` — if the new password is too short or longer than 64 characters.
- `UserNotFoundError` — if the username does not exist.

---

### `delete_user(username: str) -> None`

Delete a non-admin user account.

**Parameters:**

- `username` (`str`): Username of the account to delete.

**Returns:** `None`

**Raises:**

- `UserNotFoundError` — if the user does not exist.
- `AuthorizationError` — if the target user has the admin role.
