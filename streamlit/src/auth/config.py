import os
from dataclasses import dataclass

from .exceptions import ConfigurationError


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Invalid boolean value for {name}: {raw}")


def _read_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid integer value for {name}: {raw}") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}.")
    return value


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_connect_timeout_seconds: int
    admin_username: str
    admin_password: str
    bcrypt_rounds: int
    password_min_length: int


def load_auth_settings() -> AuthSettings:
    return AuthSettings(
        enabled=_read_bool("AUTH_ENABLED", True),
        db_host=os.getenv("DB_HOST", "postgres"),
        db_port=_read_int("DB_PORT", 5432),
        db_name=os.getenv("DB_NAME", "sefuse"),
        db_user=os.getenv("DB_USER", "sefuse"),
        db_password=os.getenv("DB_PASSWORD", "sefuse"),
        db_connect_timeout_seconds=_read_int("DB_CONNECT_TIMEOUT_SECONDS", 5),
        admin_username=(os.getenv("ADMIN_USERNAME") or "").strip(),
        admin_password=os.getenv("ADMIN_PASSWORD") or "",
        bcrypt_rounds=_read_int("BCRYPT_ROUNDS", 12, minimum=4),
        password_min_length=_read_int("PASSWORD_MIN_LENGTH", 8),
    )
