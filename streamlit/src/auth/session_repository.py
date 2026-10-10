"""PostgreSQL-backed session token repository for cross-tab persistence."""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from psycopg2.extras import RealDictCursor

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class SessionRepository(BaseRepository):
    """Manages persistent session tokens in the ``auth_sessions`` table.

    Tokens are cryptographically random hex strings stored alongside an
    expiry timestamp. Expired sessions are not cleaned up automatically —
    call ``cleanup_expired()`` periodically for housekeeping.
    """

    def create_session(self, user_id: int, timeout_minutes: int) -> str:
        """Create a new session token for the given user.

        Args:
            user_id: The ``auth_users.id`` of the authenticated user.
            timeout_minutes: Session lifetime in minutes.

        Returns:
            The generated 64-character hex token.
        """
        token = secrets.token_hex(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
        self._execute(
            """
            INSERT INTO auth_sessions (token, user_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (token, user_id, expires_at),
        )
        logger.info("Session created for user_id=%s", user_id)
        return token

    def validate_and_refresh(self, token: str, timeout_minutes: int) -> dict | None:
        """Validate a session token and extend its expiry (sliding window).

        Expired sessions are not actively cleaned up here — they are harmless
        because the UPDATE only matches rows where ``expires_at >= now``. Use
        ``cleanup_expired()`` for periodic housekeeping.

        Args:
            token: The session token from the browser cookie.
            timeout_minutes: New expiry window in minutes from now.

        Returns:
            Dict with keys ``user_id``, ``username``, ``role`` if valid,
            or ``None`` if the token is invalid, expired, or the user is
            inactive.
        """
        now = datetime.now(timezone.utc)
        new_expires = now + timedelta(minutes=timeout_minutes)
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    UPDATE auth_sessions SET expires_at = %s
                    WHERE token = %s AND expires_at >= %s
                    RETURNING user_id
                    """,
                    (new_expires, token, now),
                )
                row = cur.fetchone()
                if row is None:
                    conn.commit()
                    return None

                cur.execute(
                    """
                    SELECT u.id, u.username, r.name AS role
                    FROM auth_users u
                    JOIN auth_roles r ON u.role_id = r.id
                    WHERE u.id = %s AND u.is_active = TRUE
                    """,
                    (row["user_id"],),
                )
                user_row = cur.fetchone()
            conn.commit()

        if user_row is None:
            return None
        return {
            "user_id": user_row["id"],
            "username": user_row["username"],
            "role": user_row["role"],
        }

    def cleanup_expired(self) -> None:
        """Delete all expired sessions from the database.

        Intended for periodic housekeeping (e.g. called from a scheduler).
        Expired sessions are otherwise harmless — they fail the
        ``expires_at >= now`` check in ``validate_and_refresh``.
        """
        now = datetime.now(timezone.utc)
        self._execute(
            "DELETE FROM auth_sessions WHERE expires_at < %s",
            (now,),
        )
        logger.info("Expired sessions cleaned up")

    def delete_session(self, token: str) -> None:
        """Delete a specific session token (logout)."""
        self._execute(
            "DELETE FROM auth_sessions WHERE token = %s", (token,)
        )
        logger.info("Session deleted")

    def delete_user_sessions(self, user_id: int) -> None:
        """Delete all sessions for a given user."""
        self._execute(
            "DELETE FROM auth_sessions WHERE user_id = %s", (user_id,)
        )
