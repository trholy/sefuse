import re

import bcrypt

from .config import AuthSettings
from .exceptions import ValidationError

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{4,16}$")
DUMMY_BCRYPT_HASH = "$2b$12$wP8v2D3Y1IK6otD8QmVfQeTHkFnNf2u8J2RIPfpaF.6vP5lSIlm2."


def normalize_username(username: str) -> str:
    normalized = (username or "").strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValidationError(
            "Username must be 4-16 characters and only contain letters,"
            " numbers, underscores, or hyphens."
        )
    return normalized


def validate_password_strength(password: str, settings: AuthSettings) -> None:
    if not password:
        raise ValidationError("Password is required.")
    if len(password) < settings.password_min_length:
        raise ValidationError(
            f"Password must be at least {settings.password_min_length}-64 characters long."
        )
    if len(password) > 64:
        raise ValidationError("Password is too long.")


class PasswordHasher:
    def __init__(self, rounds: int = 12):
        self._rounds = rounds

    def hash_password(self, plain_password: str) -> str:
        password_bytes = plain_password.encode("utf-8")
        return bcrypt.hashpw(
            password_bytes,
            bcrypt.gensalt(rounds=self._rounds),
        ).decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
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
        hash_to_check = candidate_hash or DUMMY_BCRYPT_HASH
        is_valid = self.verify_password(plain_password, hash_to_check)
        return bool(candidate_hash) and is_valid
