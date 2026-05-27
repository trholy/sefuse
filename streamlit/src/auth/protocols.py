from typing import Protocol

from .models import UserRecord, UserSummary


class UserRepositoryProtocol(Protocol):
    """Structural interface for user persistence backends.

    Implementations must provide CRUD operations over user accounts. Both
    `PostgresUserRepository` and any test doubles must satisfy this protocol.
    """

    def get_by_username(self, username: str) -> UserRecord | None:
        """Fetch a full user record by username.

        Args:
            username (str): Normalised (lowercase) username to look up.

        Returns:
            UserRecord | None: Record with hashed password, or None if not found.
        """
        ...

    def list_users(self) -> list[UserSummary]:
        """Return all users as public summaries.

        Returns:
            list[UserSummary]: Summaries without password hashes, sorted alphabetically.
        """
        ...

    def create_user(self, username: str, password_hash: str, role: str) -> UserRecord:
        """Persist a new user and return the created record.

        Args:
            username (str): Normalised username.
            password_hash (str): bcrypt hash of the user's password.
            role (str): Role name (must exist in the backing store).

        Returns:
            UserRecord: The newly created user record.

        Raises:
            UserAlreadyExistsError: If the username is already taken.
        """
        ...

    def update_password_hash(self, username: str, password_hash: str) -> None:
        """Replace the stored password hash for an existing user.

        Args:
            username (str): Normalised username of the account to update.
            password_hash (str): New bcrypt hash.

        Raises:
            UserNotFoundError: If no user with that username exists.
        """
        ...

    def delete_user(self, username: str) -> None:
        """Remove a user account from the backing store.

        Args:
            username (str): Normalised username to delete.

        Raises:
            UserNotFoundError: If no user with that username exists.
        """
        ...

