# `shared.secrets_box`

Symmetric encryption for user secrets held in PostgreSQL.

Used for `auth_users.gotify_token`. The alert job has to send the actual token in the `X-Gotify-Key` header, so the value must be recoverable and a one-way hash cannot be used. Fernet encryption keeps the token unreadable in a database dump or backup while the service can still use it.

The key comes from `GOTIFY_SECRET_KEY` and is required whenever Gotify is enabled. A missing or placeholder key raises; there is no fallback to storing plaintext.

Generate a key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Rotating the key invalidates every stored token. Affected users re-enter theirs on the Notification Settings page.

---

## Classes

### `SecretKeyError(RuntimeError)`

Raised when the encryption key is missing or unusable.

---

## Functions

### `encrypt(plaintext: str) -> str`

Encrypt a secret for storage.

**Parameters:**

- `plaintext` (`str`): The secret. Empty input returns `""`, so "no token configured" is stored as an empty column.

**Returns:** `str` — url-safe base64 ciphertext.

**Raises:**

- `SecretKeyError` — when `GOTIFY_SECRET_KEY` is unset, starts with `change_me`, or is not a valid Fernet key.

---

### `decrypt(ciphertext: str) -> str`

Decrypt a stored secret. Does not raise on a value that cannot be decrypted.

A value that cannot be decrypted, most likely because `GOTIFY_SECRET_KEY` was rotated, is treated as "no token configured". The nightly alert job then keeps running for every other user.

**Parameters:**

- `ciphertext` (`str`): Stored column value.

**Returns:** `str` — the plaintext secret, or `""` when absent or undecryptable.

---

### `ensure_key_available() -> None`

Validate the key at startup so that a misconfiguration fails immediately.

**Raises:**

- `SecretKeyError` — when the key is missing or unusable.
