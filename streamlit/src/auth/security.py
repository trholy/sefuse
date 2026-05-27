import re

import bcrypt

from .config import AuthSettings
from .exceptions import ValidationError

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{4,16}$")
DUMMY_BCRYPT_HASH: str = bcrypt.hashpw(b"__sentinel__", bcrypt.gensalt()).decode()


def normalize_username(username: str) -> str:
    """Strip, lowercase, and validate a username against the allowed pattern.

    Args:
        username (str): Raw username input from the login form.

    Returns:
        str: Normalised (lowercase, stripped) username.

    Raises:
        ValidationError: If the username does not match `USERNAME_PATTERN`
            (4-16 alphanumeric/underscore/hyphen characters).
    """
    normalized = (username or "").strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValidationError(
            "Username must be 4-16 characters and only contain letters,"
            " numbers, underscores, or hyphens."
        )
    return normalized


def validate_password_strength(password: str, settings: AuthSettings) -> None:
    """Check that a password meets minimum length and maximum length requirements.

    Args:
        password (str): Plain-text password to validate.
        settings (AuthSettings): Provides `password_min_length` (default 8); max is 64.

    Raises:
        ValidationError: If the password is empty, too short, or longer than 64 chars.
    """
    if not password:
        raise ValidationError("Password is required.")
    if len(password) < settings.password_min_length:
        raise ValidationError(
            f"Password must be at least {settings.password_min_length}-64 characters long."
        )
    if len(password) > 64:
        raise ValidationError("Password is too long.")


class PasswordHasher:
    """bcrypt password hashing and verification with constant-time fallback.

    Args:
        rounds (int, default=12): bcrypt cost factor. Higher values increase hashing time.

    Example:
        hasher = PasswordHasher(rounds=12)
        h = hasher.hash_password("secret")
        hasher.verify_password("secret", h)  # True
    """

    def __init__(self, rounds: int = 12):
        """Initialise the hasher with the given bcrypt cost factor.

        Args:
            rounds (int, optional): bcrypt work factor (higher = slower hashing). Defaults to 12.
        """
        self._rounds = rounds

    def hash_password(self, plain_password: str) -> str:
        """Hash a plain-text password with bcrypt.

        Args:
            plain_password (str): Password to hash.

        Returns:
            str: bcrypt hash string.
        """
        password_bytes = plain_password.encode("utf-8")
        return bcrypt.hashpw(
            password_bytes,
            bcrypt.gensalt(rounds=self._rounds),
        ).decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        """Verify a plain-text password against a stored bcrypt hash.

        Args:
            plain_password (str): Password attempt.
            password_hash (str): Stored bcrypt hash.

        Returns:
            bool: True if the password matches the hash.
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except ValueError:
            return False

    def verify_password_with_fallback(
        self,
        plain_password: str,
        candidate_hash: str | None,
    ) -> bool:
        """Verify a password, using a dummy hash when no stored hash is available.

        Performs a constant-time bcrypt check even for unknown users to prevent
        user enumeration via timing attacks.

        Args:
            plain_password (str): Password attempt.
            candidate_hash (str | None): Stored bcrypt hash, or None for unknown users.

        Returns:
            bool: True only if `candidate_hash` is not None and the password matches.
        """
        hash_to_check = candidate_hash or DUMMY_BCRYPT_HASH
        is_valid = self.verify_password(plain_password, hash_to_check)
        return bool(candidate_hash) and is_valid
