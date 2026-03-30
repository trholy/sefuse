from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class UserSummary:
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

