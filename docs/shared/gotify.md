# `shared.gotify`

Gotify push-notification client, shared by FastAPI and Streamlit.

FastAPI uses it from the nightly alert job. Streamlit uses it to verify a user's token and to send test notifications. Both talk to the one server named by `GOTIFY_URL` (see [Gotify Config](gotify_config.md)).

Every call has an explicit timeout, so an unresponsive Gotify server cannot stall the alert job. No function raises on a delivery failure: sends return `False` and log.

---

## Functions

### `is_allowed_gotify_url(url: str) -> bool`

Return whether `url` is a usable Gotify server address.

This is a sanity check on the operator-supplied `GOTIFY_URL`. It requires an http(s) URL with a host and rejects the stack's own service names (`qdrant`, `postgres`, `ollama`, `fastapi`, `streamlit`) and the container's loopback. Private and LAN addresses are allowed, because a self-hosted Gotify usually sits on the same network. Hostnames are not resolved.

**Returns:** `bool`

---

### `normalize_server_url(server_url: str) -> str`

Reduce a configured server address to a bare `scheme://host[:port]` base. Any path, query or fragment is dropped. A missing scheme defaults to `https`.

**Parameters:**

- `server_url` (`str`): Raw value, e.g. `"gotify.example.com"` or `"https://gotify.example.com/some/path"`.

**Returns:** `str` — normalised base, e.g. `"https://gotify.example.com"`; `""` for empty input.

---

### `verify_server(base_url: str, timeout: float | None = None) -> tuple[bool, str]`

Check that `base_url` is a Gotify server by calling its unauthenticated `GET /version` endpoint. A host that answers 200 without a `version` key is reported as not being a Gotify server.

**Returns:** `tuple[bool, str]` — `(ok, reason)`. `reason` is safe to show in the UI or write to a log.

---

### `verify_token(base_url: str, token: str, timeout: float | None = None) -> tuple[bool, str]`

Check that `token` is a valid application token on `base_url`.

Gotify application tokens may only write messages, so the check is a `POST /message`. This sends a real notification, which is why the UI presents it as "verify and send a test notification".

**Returns:** `tuple[bool, str]` — `(ok, reason)`. `reason` is safe to show in the UI.

---

## Classes

### `GotifyClient`

Sends messages to one user's channel on the Gotify server.

**Parameters:**

- `token` (`str`): The user's Gotify application token. An empty token turns every send into a logged no-op.
- `base` (`str | None`): Server base URL. Defaults to the configured `GOTIFY_URL`.
- `priority` (`int | None`): Message priority. Defaults to `GOTIFY_PRIORITY`.
- `timeout` (`float | None`): HTTP timeout. Defaults to `GOTIFY_TIMEOUT_SECONDS`.

#### `send(title: str, message: str, *, markdown: bool = True) -> bool`

Push one message. Never raises: transport errors and rejections are logged and reported as `False`.

**Parameters:**

- `title` (`str`): Notification title.
- `message` (`str`): Body. May contain markdown when `markdown` is set.
- `markdown` (`bool`): Ask clients to render the body as markdown, which turns an embedded `[name](url)` into a tappable link.

**Returns:** `bool` — `True` on a 2xx response.
