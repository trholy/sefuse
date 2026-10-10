# `shared.env`

Boolean environment-value parsing shared by FastAPI and Streamlit.

Only the vocabulary lives here, not the policy. The readers that use it react differently, on purpose, to a value they cannot read:

| Reader | Reaction to an unreadable value |
|---|---|
| `fastapi/src/utils/env.py`, `shared/gotify_config.py` | Fall back to the caller's default. |
| `shared/alerts_config.py` | Treat it as off — a master switch that fails open is worse than one that fails closed. |
| `streamlit/src/auth/config.py` | Raise `ConfigurationError` — a typo in `AUTH_ENABLED` must not quietly leave a deployment unauthenticated. |

The module imports nothing beyond the standard library, so it is importable from either container.

---

## Constants

| Constant | Type | Value | Description |
|---|---|---|---|
| `TRUTHY` | `frozenset[str]` | `{"1", "true", "yes", "on"}` | Spellings read as `True`. |
| `FALSY` | `frozenset[str]` | `{"0", "false", "no", "off"}` | Spellings read as `False`. |

Changing either set changes what every deployment's `.env` means.

---

## Functions

### `parse_bool(raw: str | None) -> bool | None`

Parse an environment value as a boolean. Matching is case-insensitive and ignores surrounding whitespace.

**Parameters:**

- `raw` (`str | None`): Raw value as read from the environment, or `None` when the variable is unset.

**Returns:** `bool | None` — `True` or `False` for a recognised spelling; `None` when the variable is unset or holds text that is not a boolean.

`None` covers both "unset" and "unreadable". A caller that treats the two differently checks `raw is None` first.
