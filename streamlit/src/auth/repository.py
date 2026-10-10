from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

from .base_repository import BaseRepository
from .db import Database
from .exceptions import UserAlreadyExistsError, UserNotFoundError
from .models import UserRecord, UserSummary


def _to_user_record_returning(row: dict) -> UserRecord:
    """Map a RETURNING row (with role name already joined) to a ``UserRecord``."""
    return UserRecord(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        failed_login_attempts=row.get("failed_login_attempts", 0) or 0,
        locked_until=row.get("locked_until"),
    )


def _to_user_record(row: dict) -> UserRecord:
    """Map a `RealDictCursor` row (including `password_hash`) to a `UserRecord`."""
    return UserRecord(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        failed_login_attempts=row.get("failed_login_attempts", 0) or 0,
        locked_until=row.get("locked_until"),
    )


def _to_user_summary(row: dict) -> UserSummary:
    """Map a `RealDictCursor` row (without `password_hash`) to a `UserSummary`."""
    return UserSummary(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresUserRepository(BaseRepository):
    """PostgreSQL-backed user repository using parameterised psycopg2 queries.

    All write operations commit immediately. Raises domain exceptions
    (`UserAlreadyExistsError`, `UserNotFoundError`) instead of raw DB errors.

    Args:
        database (Database): Connection pool factory.
    """

    def get_by_username(self, username: str) -> UserRecord | None:
        """Fetch a full user record by username, or return None if not found.

        Args:
            username (str): Normalised (lowercase) username to look up.

        Returns:
            UserRecord | None: Record with hashed password, or None.
        """
        row = self._execute(
            """
            SELECT
                u.id,
                u.username,
                u.password_hash,
                r.name AS role,
                u.is_active,
                u.created_at,
                u.updated_at,
                u.failed_login_attempts,
                u.locked_until
            FROM auth_users AS u
            INNER JOIN auth_roles AS r ON u.role_id = r.id
            WHERE u.username = %s
            """,
            (username,),
            fetchone=True,
        )
        return _to_user_record(row) if row else None

    def list_users(self) -> list[UserSummary]:
        """Return all users sorted alphabetically by username.

        Returns:
            list[UserSummary]: Public summaries without password hashes.
        """
        rows = self._execute(
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
            """,
            fetch=True,
        )
        return [_to_user_summary(row) for row in rows]

    def create_user(self, username: str, password_hash: str, role: str) -> UserRecord:
        """Insert a new active user and return the created record.

        Uses ``RETURNING`` to retrieve the created row in a single round-trip
        without a follow-up ``get_by_username`` call.

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
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO auth_users (username, password_hash, role_id, is_active)
                        VALUES (
                            %s,
                            %s,
                            (SELECT id FROM auth_roles WHERE name = %s),
                            TRUE
                        )
                        RETURNING
                            id,
                            username,
                            password_hash,
                            (SELECT name FROM auth_roles WHERE name = %s) AS role,
                            is_active,
                            created_at,
                            updated_at
                        """,
                        (username, password_hash, role, role),
                    )
                    row = cursor.fetchone()
                connection.commit()
        except IntegrityError as exc:
            raise UserAlreadyExistsError("Username already exists.") from exc

        if row is None:
            raise UserNotFoundError("User creation failed unexpectedly.")
        return _to_user_record_returning(row)

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

    def get_gotify_token(self, user_id: int) -> str:
        """Return a user's decrypted Gotify app token, or ``""`` if unset.

        The column holds Fernet ciphertext; an undecryptable value (most likely
        after a ``GOTIFY_SECRET_KEY`` rotation) comes back as ``""``, i.e. as
        "not configured".

        Args:
            user_id (int): User whose token to read.
        """
        from shared.secrets_box import decrypt

        row = self._execute(
            "SELECT gotify_token FROM auth_users WHERE id = %s",
            (user_id,),
            fetchone=True,
        )
        if not row:
            return ""
        return decrypt(row["gotify_token"] or "")

    def update_gotify_token(self, user_id: int, token: str) -> None:
        """Store a user's Gotify app token, encrypted at rest.

        Args:
            user_id (int): User to update.
            token (str): Plaintext application token. An empty string clears
                the configuration.

        Raises:
            UserNotFoundError: If no user with that id exists.
        """
        from shared.secrets_box import encrypt

        stored = encrypt(token.strip()) if token else ""
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_users
                    SET gotify_token = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (stored, user_id),
                )
                if cursor.rowcount == 0:
                    raise UserNotFoundError("User does not exist.")
            connection.commit()

    def set_active(self, username: str, active: bool) -> None:
        """Set the is_active flag for a user.

        Args:
            username (str): Normalised username.
            active (bool): New active state.

        Raises:
            UserNotFoundError: If no user with that username exists.
        """
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_users
                    SET is_active = %s, updated_at = NOW()
                    WHERE username = %s
                    """,
                    (active, username),
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

    def increment_failed_login(
        self, username: str, max_attempts: int, lockout_minutes: int
    ) -> None:
        """Increment the failed login counter and lock the account if the threshold is reached.

        Args:
            username (str): Normalised username.
            max_attempts (int): Number of failures before the account is locked.
            lockout_minutes (int): How long the lockout lasts.
        """
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_users
                    SET
                        failed_login_attempts = failed_login_attempts + 1,
                        locked_until = CASE
                            WHEN failed_login_attempts + 1 >= %s
                            THEN NOW() + (%s * INTERVAL '1 minute')
                            ELSE locked_until
                        END,
                        updated_at = NOW()
                    WHERE username = %s
                    """,
                    (max_attempts, lockout_minutes, username),
                )
            connection.commit()

    def reset_failed_login(self, username: str) -> None:
        """Reset the failed login counter and clear any lockout for a user.

        Args:
            username (str): Normalised username.
        """
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_users
                    SET failed_login_attempts = 0, locked_until = NULL, updated_at = NOW()
                    WHERE username = %s
                    """,
                    (username,),
                )
            connection.commit()
