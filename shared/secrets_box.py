"""Symmetric encryption for user secrets held in Postgres.

Used for ``auth_users.gotify_token``. The alert job has to send the *actual*
token in the ``X-Gotify-Key`` header, so the value must be recoverable — a hash
would be one-way and unusable. Fernet (AES-128-CBC + HMAC) gives the intended
protection instead: the plaintext token is not readable from a database dump or
a stray backup, but the service can still use it.

The key comes from ``GOTIFY_SECRET_KEY`` and is required whenever Gotify is
enabled; a missing or placeholder key raises rather than silently falling back
to storing plaintext.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PLACEHOLDER_PREFIX = "change_me"


class SecretKeyError(RuntimeError):
    """Raised when the encryption key is missing or unusable."""


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build the Fernet instance from ``GOTIFY_SECRET_KEY``.

    Raises:
        SecretKeyError: When the key is unset, still the placeholder, or not a
            valid 32-byte url-safe base64 Fernet key.
    """
    raw = (os.getenv("GOTIFY_SECRET_KEY") or "").strip()
    if not raw:
        raise SecretKeyError(
            "GOTIFY_SECRET_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    if raw.startswith(_PLACEHOLDER_PREFIX):
        raise SecretKeyError(
            "GOTIFY_SECRET_KEY is still the placeholder value. Generate a real "
            "key before enabling Gotify."
        )
    try:
        return Fernet(raw.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise SecretKeyError(
            "GOTIFY_SECRET_KEY is not a valid Fernet key (expected url-safe "
            "base64 of 32 bytes)."
        ) from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a secret for storage.

    Args:
        plaintext (str): The secret. Empty input returns ``""`` so "no token
            configured" round-trips as an empty column rather than ciphertext.

    Returns:
        str: Url-safe base64 ciphertext.

    Raises:
        SecretKeyError: When ``GOTIFY_SECRET_KEY`` is unusable.
    """
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored secret, degrading to ``""`` rather than raising.

    A value that cannot be decrypted — most likely because ``GOTIFY_SECRET_KEY``
    was rotated — is treated as "no token configured". That keeps the nightly
    alert job running for every other user instead of failing the whole run,
    and the affected user simply re-enters their token.

    Args:
        ciphertext (str): Stored column value.

    Returns:
        str: The plaintext secret, or ``""`` when absent or undecryptable.
    """
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, SecretKeyError, ValueError, TypeError):
        logger.warning(
            "Stored secret could not be decrypted; treating it as unset. "
            "This is expected if GOTIFY_SECRET_KEY was rotated."
        )
        return ""


def ensure_key_available() -> None:
    """Validate the key at startup so misconfiguration fails loudly, not silently.

    Raises:
        SecretKeyError: When the key is missing or unusable.
    """
    _get_fernet()
