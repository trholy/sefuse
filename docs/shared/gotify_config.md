# `shared.gotify_config`

Deployment-wide Gotify settings, shared by FastAPI and Streamlit.

SeFuSe pushes alerts through a single Gotify server that the operator runs. Its URL is set in the environment and is never entered by users. What varies per user is the application token, which is that user's private channel on the shared server (see [Secrets Box](secrets_box.md) for how tokens are stored).

Configuration errors raise `GotifyConfigError` instead of exiting, because the two services react differently: FastAPI aborts startup, while Streamlit reports push as switched off.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `GOTIFY_ENABLED` | `false` | Master switch for push notifications. Implied off by `ALERTS_ENABLED=false`. |
| `GOTIFY_URL` | — | Base URL of the Gotify server, e.g. `https://gotify.example.com` or `http://192.168.1.20:8080`. Required when enabled. |
| `GOTIFY_SECRET_KEY` | — | Fernet key that encrypts users' tokens. Required when enabled. |
| `GOTIFY_PRIORITY` | `5` | Default message priority, 0–10. |
| `GOTIFY_TIMEOUT_SECONDS` | `10` | HTTP timeout for every call to Gotify. |

Both services must be given the same values.

---

## Constants

| Constant | Type | Value | Description |
|---|---|---|---|
| `DEFAULT_PRIORITY` | `int` | `5` | Priority used when `GOTIFY_PRIORITY` is unset. |
| `DEFAULT_TIMEOUT_SECONDS` | `float` | `10.0` | Timeout used when `GOTIFY_TIMEOUT_SECONDS` is unset. |

---

## Classes

### `GotifyConfigError(RuntimeError)`

Raised when Gotify is enabled but misconfigured.

### `GotifyConfig`

Resolved Gotify settings for this deployment.

| Attribute | Type | Description |
|---|---|---|
| `enabled` | `bool` | Value of `GOTIFY_ENABLED`. When `False`, the remaining fields are defaults and are never used. |
| `base_url` | `str` | Normalised base URL of the server, without a trailing slash. Empty when disabled. |
| `priority` | `int` | Default message priority. |
| `timeout` | `float` | HTTP timeout in seconds. |

---

## Functions

### `get_gotify_config() -> GotifyConfig`

Read and validate the Gotify environment. The result is cached with `lru_cache`.

**Returns:** `GotifyConfig` — the resolved settings.

**Raises:**

- `GotifyConfigError` — when enabled but `GOTIFY_URL` is missing or is not a usable http(s) URL, or the priority or timeout values are unusable.

---

### `push_enabled() -> bool`

Return whether Gotify push is switched on and usable.

`ALERTS_ENABLED` is checked first, because push is part of the alert feature. A misconfiguration is logged and reported as `False` instead of raised: Streamlit would otherwise fail on every page over a bad `GOTIFY_URL`, and the alert run delivers in-app notifications in that case.

**Returns:** `bool` — `True` when alerts are on and the Gotify configuration loads and is enabled.
