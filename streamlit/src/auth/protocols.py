from typing import Protocol

from .models import UserRecord, UserSummary


class UserRepositoryProtocol(Protocol):
    def get_by_username(self, username: str) -> UserRecord | None:
        pass

    def list_users(self) -> list[UserSummary]:
        pass

    def create_user(self, username: str, password_hash: str, role: str) -> UserRecord:
        pass

    def update_password_hash(self, username: str, password_hash: str) -> None:
        pass

    def delete_user(self, username: str) -> None:
        pass

