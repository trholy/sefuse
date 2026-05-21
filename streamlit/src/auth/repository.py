from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

from .db import Database
from .exceptions import UserAlreadyExistsError, UserNotFoundError
from .models import UserRecord, UserSummary


def _to_user_record(row: dict) -> UserRecord:
    return UserRecord(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_user_summary(row: dict) -> UserSummary:
    return UserSummary(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresUserRepository:
    """PostgreSQL-backed user repository using parameterised psycopg2 queries.

    All write operations commit immediately. Raises domain exceptions
    (`UserAlreadyExistsError`, `UserNotFoundError`) instead of raw DB errors.

    Args:
        database (Database): Connection factory.
    """

    def __init__(self, database: Database):
        self._database = database

    def get_by_username(self, username: str) -> UserRecord | None:
        """Fetch a full user record by username, or return None if not found.

        Args:
            username (str): Normalised (lowercase) username to look up.

        Returns:
            UserRecord | None: Record with hashed password, or None.
        """
        with self._database.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.id,
                        u.username,
                        u.password_hash,
                        r.name AS role,
                        u.is_active,
                        u.created_at,
                        u.updated_at
                    FROM auth_users AS u
                    INNER JOIN auth_roles AS r ON u.role_id = r.id
                    WHERE u.username = %s
                    """,
                    (username,),
                )
                row = cursor.fetchone()
        return _to_user_record(row) if row else None

    def list_users(self) -> list[UserSummary]:
        """Return all users sorted alphabetically by username.

        Returns:
            list[UserSummary]: Public summaries without password hashes.
        """
        with self._database.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.id,
                        u.username,
                        r.name AS role,
                        u.is_active,
                        u.created_at,
                        u.updated_at
                    FROM auth_users AS u
                    INNER JOIN auth_roles AS r ON u.role_id = r.id
                    ORDER BY u.username ASC
                    """
                )
                rows = cursor.fetchall()
        return [_to_user_summary(row) for row in rows]

    def create_user(self, username: str, password_hash: str, role: str) -> UserRecord:
        """Insert a new active user and return the created record.

        Args:
            username (str): Normalised username.
            password_hash (str): bcrypt hash of the user's password.
            role (str): Role name that must exist in the `auth_roles` table.

        Returns:
            UserRecord: The newly created user record.

        Raises:
            UserAlreadyExistsError: If the username is already taken.
        """
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO auth_users (username, password_hash, role_id, is_active)
                        VALUES (
                            %s,
                            %s,
                            (SELECT id FROM auth_roles WHERE name = %s),
                            TRUE
                        )
                        """,
                        (username, password_hash, role),
                    )
                connection.commit()
        except IntegrityError as exc:
            raise UserAlreadyExistsError("Username already exists.") from exc

        created_user = self.get_by_username(username)
        if created_user is None:
            raise UserNotFoundError("User creation failed unexpectedly.")
        return created_user

    def update_password_hash(self, username: str, password_hash: str) -> None:
        """Update the password hash for an existing user.

        Args:
            username (str): Normalised username of the user to update.
            password_hash (str): New bcrypt hash.

        Raises:
            UserNotFoundError: If no user with that username exists.
        """
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_users
                    SET password_hash = %s, updated_at = NOW()
                    WHERE username = %s
                    """,
                    (password_hash, username),
                )
                if cursor.rowcount == 0:
                    raise UserNotFoundError("User does not exist.")
            connection.commit()

    def delete_user(self, username: str) -> None:
        """Delete a user by username.

        Args:
            username (str): Normalised username to delete.

        Raises:
            UserNotFoundError: If no user with that username exists.
        """
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM auth_users WHERE username = %s",
                    (username,),
                )
                if cursor.rowcount == 0:
                    raise UserNotFoundError("User does not exist.")
            connection.commit()
