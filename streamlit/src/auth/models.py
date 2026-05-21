from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserRecord:
    """Full user record including the bcrypt password hash, returned by the repository layer.

    Not exposed to the UI; used internally by authentication services.
    """

    id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class UserSummary:
    """Public user summary without the password hash, used for admin user-management views."""

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

