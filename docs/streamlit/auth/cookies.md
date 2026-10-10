# `streamlit.auth.cookies`

Browser cookie handling for keeping a login across browser tabs and page reloads.

Streamlit session state belongs to one browser tab. To carry a login to other tabs, a session token is stored in a browser cookie and validated against the `auth_sessions` table (see `SessionRepository` in [Repositories](repositories.md)).

The cookie is read through `st.context.cookies`, which is read-only. It is set and cleared by injecting a zero-height `<script>` through `st.components.v1.html()`.

| Variable | Default | Description |
|---|---|---|
| `SESSION_COOKIES_ENABLED` | `true` | `false` disables the cookie; each browser tab then needs its own login. |
| `SESSION_COOKIE_SECURE` | `false` | `true` adds the `Secure` attribute, so the cookie is only sent over HTTPS. Leave `false` for a plain `http://localhost` deployment. |

---

## Functions

### `read_session_cookie() -> str | None`

Read the session token from the browser cookie.

**Returns:** `str | None` — the token, or `None` if no session cookie is present.

---

### `set_session_cookie(token: str, max_age_seconds: int, *, reload: bool = False, secure: bool = False) -> None`

Set the session cookie in the browser. Runs at most once per Streamlit render cycle.

**Parameters:**

- `token` (`str`): Session token to store.
- `max_age_seconds` (`int`): Cookie lifetime in seconds.
- `reload` (`bool`): If `True`, the script also reloads the parent page, so that `st.context.cookies` sees the cookie on the next server round-trip.
- `secure` (`bool`): If `True`, append the `Secure` attribute.

**Returns:** `None`

---

### `clear_session_cookie(*, reload: bool = False, secure: bool = False) -> None`

Delete the session cookie by setting it with `max-age=0`.

**Parameters:**

- `reload` (`bool`): If `True`, reload the parent page after clearing.
- `secure` (`bool`): If `True`, append the `Secure` attribute, so the deletion matches a cookie that was set with `Secure`.

**Returns:** `None`
