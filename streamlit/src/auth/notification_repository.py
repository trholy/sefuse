"""PostgreSQL-backed in-app alert notification persistence."""

from dataclasses import dataclass
from datetime import datetime

from .base_repository import BaseRepository


@dataclass(frozen=True)
class AlertNotification:
    """A single in-app alert notification."""

    id: int
    user_id: int
    saved_search_id: int
    project_id: str
    project_title: str
    project_website: str
    matching_score: float
    is_read: bool
    created_at: datetime


class NotificationRepository(BaseRepository):
    """CRUD operations on the ``alert_notifications`` table."""

    def get_unread_count(self, user_id: int) -> int:
        """Return the number of unread notifications for a user."""
        row = self._execute(
            """
            SELECT COUNT(*) AS count FROM alert_notifications
            WHERE user_id = %s AND is_read = FALSE
            """,
            (user_id,),
            fetchone=True,
        )
        return row["count"] if row else 0

    def get_unread(self, user_id: int) -> list[AlertNotification]:
        """Return unread notifications for a user, newest first."""
        rows = self._execute(
            """
            SELECT n.id, n.user_id, n.saved_search_id,
                   n.project_id, n.project_title, n.project_website,
                   n.matching_score, n.is_read, n.created_at
            FROM alert_notifications n
            WHERE n.user_id = %s AND n.is_read = FALSE
            ORDER BY n.created_at DESC
            """,
            (user_id,),
            fetch=True,
        )
        return [AlertNotification(**row) for row in rows]

    def mark_read(self, notification_id: int, user_id: int) -> None:
        """Mark a single notification as read."""
        self._execute(
            """
            UPDATE alert_notifications SET is_read = TRUE
            WHERE id = %s AND user_id = %s
            """,
            (notification_id, user_id),
        )

    def get_recent(
        self, user_id: int, limit: int = 50
    ) -> list[AlertNotification]:
        """Return a user's notifications, read and unread, newest first.

        ``get_unread`` alone leaves the alerts panel empty as soon as the user
        marks things read, which reads as "the feature is broken". This backs a
        panel that still shows recent history.

        Args:
            user_id (int): Owner of the notifications.
            limit (int): Maximum rows to return.
        """
        rows = self._execute(
            """
            SELECT n.id, n.user_id, n.saved_search_id,
                   n.project_id, n.project_title, n.project_website,
                   n.matching_score, n.is_read, n.created_at
            FROM alert_notifications n
            WHERE n.user_id = %s
            ORDER BY n.created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
            fetch=True,
        )
        return [AlertNotification(**row) for row in rows]

    def mark_all_read(self, user_id: int) -> None:
        """Mark all unread notifications for a user as read."""
        self._execute(
            """
            UPDATE alert_notifications SET is_read = TRUE
            WHERE user_id = %s AND is_read = FALSE
            """,
            (user_id,),
        )

    def delete(self, notification_id: int, user_id: int) -> None:
        """Delete a single notification, scoped to its owner."""
        self._execute(
            """
            DELETE FROM alert_notifications
            WHERE id = %s AND user_id = %s
            """,
            (notification_id, user_id),
        )

    def delete_all(self, user_id: int) -> None:
        """Delete every notification belonging to a user."""
        self._execute(
            "DELETE FROM alert_notifications WHERE user_id = %s",
            (user_id,),
        )
