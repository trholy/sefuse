from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UserRecord:
    """Full user record including the bcrypt password hash, returned by the repository layer.

    Not exposed to the UI; used internally by authentication services.

    Attributes:
        id (int): Auto-incremented primary key from the database.
        username (str): Normalised (lowercase) username.
        password_hash (str): bcrypt hash of the user's password.
        role (str): Assigned role name, e.g. ``"user"`` or ``"admin"``.
        is_active (bool): Whether the account is active and may log in.
        created_at (datetime): Timestamp of account creation (UTC).
        updated_at (datetime): Timestamp of last account update (UTC).
        failed_login_attempts (int): Count of consecutive failed login attempts.
        locked_until (datetime | None): Lockout expiry timestamp; None if not locked.
    """

    id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


@dataclass(frozen=True)
class UserSummary:
    """Public user summary without the password hash, used for admin user-management views.

    Attributes:
        id (int): Auto-incremented primary key from the database.
        username (str): Normalised (lowercase) username.
        role (str): Assigned role name, e.g. ``"user"`` or ``"admin"``.
        is_active (bool): Whether the account is active and may log in.
        created_at (datetime): Timestamp of account creation (UTC).
        updated_at (datetime): Timestamp of last account update (UTC).
    """

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

