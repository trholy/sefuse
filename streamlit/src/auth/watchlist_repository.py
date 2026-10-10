"""PostgreSQL-backed watchlist persistence."""

from dataclasses import dataclass
from datetime import datetime

from .base_repository import BaseRepository


@dataclass(frozen=True)
class WatchlistItem:
    """A single watchlisted project."""

    id: int
    user_id: int
    project_id: str
    collection_type: str
    project_title: str
    project_website: str
    added_at: datetime


class WatchlistRepository(BaseRepository):
    """CRUD operations on the ``user_watchlist`` table."""

    def get_watchlisted_ids(
        self, user_id: int, collection_type: str
    ) -> set[str]:
        """Return project IDs the user has watchlisted for a collection.

        Args:
            user_id: ``auth_users.id``.
            collection_type: ``'german'`` or ``'eu'``.

        Returns:
            Set of project-ID strings.
        """
        rows = self._execute(
            """
            SELECT project_id FROM user_watchlist
            WHERE user_id = %s AND collection_type = %s
            """,
            (user_id, collection_type),
            fetch=True,
        )
        return {row["project_id"] for row in rows}

    def add(
        self,
        user_id: int,
        project_id: str,
        collection_type: str,
        project_title: str,
        project_website: str,
    ) -> None:
        """Add a project to the user's watchlist. No-op on duplicate."""
        self._execute(
            """
            INSERT INTO user_watchlist
                (user_id, project_id, collection_type,
                 project_title, project_website)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, project_id, collection_type) DO NOTHING
            """,
            (
                user_id,
                project_id,
                collection_type,
                project_title,
                project_website,
            ),
        )

    def remove(
        self, user_id: int, project_id: str, collection_type: str
    ) -> None:
        """Remove a project from the user's watchlist."""
        self._execute(
            """
            DELETE FROM user_watchlist
            WHERE user_id = %s AND project_id = %s
                  AND collection_type = %s
            """,
            (user_id, project_id, collection_type),
        )

    def list_items(self, user_id: int) -> list[WatchlistItem]:
        """Return all watchlisted items for a user, newest first."""
        rows = self._execute(
            """
            SELECT id, user_id, project_id, collection_type,
                   project_title, project_website, added_at
            FROM user_watchlist
            WHERE user_id = %s
            ORDER BY added_at DESC
            """,
            (user_id,),
            fetch=True,
        )
        return [WatchlistItem(**row) for row in rows]

    def list_items_by_collection(
        self, user_id: int, collection_type: str
    ) -> list[WatchlistItem]:
        """Return watchlisted items filtered by collection type."""
        rows = self._execute(
            """
            SELECT id, user_id, project_id, collection_type,
                   project_title, project_website, added_at
            FROM user_watchlist
            WHERE user_id = %s AND collection_type = %s
            ORDER BY added_at DESC
            """,
            (user_id, collection_type),
            fetch=True,
        )
        return [WatchlistItem(**row) for row in rows]
