import os
from dataclasses import dataclass

from .exceptions import ConfigurationError


def _read_bool(name: str, default: bool) -> bool:
    """Read an environment variable and coerce it to a boolean.

    Args:
        name (str): Environment variable name.
        default (bool): Value to return when the variable is unset.

    Returns:
        bool: Parsed boolean value.

    Raises:
        ConfigurationError: If the variable is set but not a recognised truthy/falsy string.
    """
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
    """Read an environment variable and coerce it to an integer with a minimum bound.

    Args:
        name (str): Environment variable name.
        default (int): Value to return when the variable is unset.
        minimum (int, optional): Inclusive lower bound for the parsed value. Defaults to 1.

    Returns:
        int: Parsed integer value.

    Raises:
        ConfigurationError: If the variable is set but cannot be parsed as an integer,
            or if the parsed value is below `minimum`.
    """
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
    """Immutable auth configuration resolved from environment variables.

    All fields are populated by `load_auth_settings`; do not instantiate directly.

    Attributes:
        enabled (bool): Whether authentication is active (``AUTH_ENABLED``).
        db_host (str): PostgreSQL host (``DB_HOST``).
        db_port (int): PostgreSQL port (``DB_PORT``).
        db_name (str): Database name (``DB_NAME``).
        db_user (str): Database user (``DB_USER``).
        db_password (str): Database password (``DB_PASSWORD``).
        db_connect_timeout_seconds (int): psycopg2 connection timeout (``DB_CONNECT_TIMEOUT_SECONDS``).
        admin_username (str): Bootstrap admin username (``ADMIN_USERNAME``).
        admin_password (str): Bootstrap admin password (``ADMIN_PASSWORD``).
        bcrypt_rounds (int): bcrypt cost factor; minimum 4 (``BCRYPT_ROUNDS``).
        password_min_length (int): Minimum password length enforced at creation (``PASSWORD_MIN_LENGTH``).
        session_timeout_minutes (int): Idle session expiry in minutes (``SESSION_TIMEOUT_MINUTES``).
    """

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
    session_timeout_minutes: int


def load_auth_settings() -> AuthSettings:
    """Read and validate auth configuration from environment variables.

    Returns:
        AuthSettings: Populated settings dataclass.

    Raises:
        ConfigurationError: If a required env var has an invalid boolean/integer value,
            `BCRYPT_ROUNDS < 4`, or `DB_PASSWORD` is empty while auth is enabled.
    """
    enabled = _read_bool("AUTH_ENABLED", True)
    db_password = os.getenv("DB_PASSWORD", "")
    if enabled and not db_password:
        raise ConfigurationError(
            "DB_PASSWORD must be set when AUTH_ENABLED=true."
        )
    return AuthSettings(
        enabled=enabled,
        db_host=os.getenv("DB_HOST", "postgres"),
        db_port=_read_int("DB_PORT", 5432),
        db_name=os.getenv("DB_NAME", "sefuse"),
        db_user=os.getenv("DB_USER", "sefuse"),
        db_password=db_password,
        db_connect_timeout_seconds=_read_int("DB_CONNECT_TIMEOUT_SECONDS", 5),
        admin_username=(os.getenv("ADMIN_USERNAME") or "").strip(),
        admin_password=os.getenv("ADMIN_PASSWORD") or "",
        bcrypt_rounds=_read_int("BCRYPT_ROUNDS", 12, minimum=4),
        password_min_length=_read_int("PASSWORD_MIN_LENGTH", 8),
        session_timeout_minutes=_read_int("SESSION_TIMEOUT_MINUTES", 30),
    )
