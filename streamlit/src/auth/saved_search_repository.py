"""PostgreSQL-backed saved search persistence."""

from dataclasses import dataclass
from datetime import datetime

from psycopg2.extras import Json

from shared.alert_levels import DEFAULT_LEVEL, LEVELS, normalize_level

from .base_repository import BaseRepository


@dataclass(frozen=True)
class SavedSearch:
    """A saved search with optional alert configuration."""

    id: int
    user_id: int
    title: str
    query_text: str
    collection_type: str
    filters: dict
    semantic_weight: float
    search_limit: int
    alert_enabled: bool
    alert_level: str
    alert_last_run: datetime | None
    alert_known_project_ids: list[str]
    alert_baseline_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _to_saved_search(row: dict) -> SavedSearch:
    """Map a ``RealDictCursor`` row to a ``SavedSearch`` dataclass."""
    return SavedSearch(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        query_text=row["query_text"],
        collection_type=row["collection_type"],
        filters=row["filters"] if isinstance(row["filters"], dict) else {},
        semantic_weight=float(row["semantic_weight"]),
        search_limit=int(row["search_limit"]),
        alert_enabled=bool(row["alert_enabled"]),
        alert_level=normalize_level(row.get("alert_level", DEFAULT_LEVEL)),
        alert_last_run=row["alert_last_run"],
        alert_known_project_ids=list(row["alert_known_project_ids"] or []),
        alert_baseline_at=row.get("alert_baseline_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SavedSearchRepository(BaseRepository):
    """CRUD operations on the ``saved_searches`` table."""

    def create(
        self,
        user_id: int,
        title: str,
        query_text: str,
        collection_type: str,
        filters: dict,
        semantic_weight: float,
        search_limit: int,
    ) -> int:
        """Create a new saved search and return its ID."""
        row = self._execute(
            """
            INSERT INTO saved_searches
                (user_id, title, query_text, collection_type,
                 filters, semantic_weight, search_limit)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                title,
                query_text,
                collection_type,
                Json(filters),
                semantic_weight,
                search_limit,
            ),
            fetchone=True,
        )
        return row["id"]

    def find_duplicate(
        self,
        user_id: int,
        query_text: str,
        collection_type: str,
        filters: dict,
        semantic_weight: float,
    ) -> SavedSearch | None:
        """Return the user's existing saved search identical to these parameters.

        Two searches are the same when the query, collection, filters and
        semantic weight all match; the title and result limit do not make it a
        different search. Saving the same search twice would push every alert
        twice, so callers check this before `create`.

        This is an application-level check, not a database constraint, so two
        saves racing each other can still both get through.
        """
        row = self._execute(
            """
            SELECT * FROM saved_searches
            WHERE user_id = %s
              AND collection_type = %s
              AND query_text = %s
              AND filters = %s
              AND semantic_weight = %s::real
            ORDER BY id
            LIMIT 1
            """,
            (user_id, collection_type, query_text, Json(filters), semantic_weight),
            fetchone=True,
        )
        return _to_saved_search(row) if row else None

    def list_by_user(self, user_id: int) -> list[SavedSearch]:
        """Return all saved searches for a user, newest first."""
        rows = self._execute(
            """
            SELECT * FROM saved_searches
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
            fetch=True,
        )
        return [_to_saved_search(row) for row in rows]

    def get_by_id(self, search_id: int, user_id: int) -> SavedSearch | None:
        """Fetch a single saved search, scoped to the user."""
        row = self._execute(
            "SELECT * FROM saved_searches WHERE id = %s AND user_id = %s",
            (search_id, user_id),
            fetchone=True,
        )
        return _to_saved_search(row) if row else None

    def delete(self, search_id: int, user_id: int) -> None:
        """Delete a saved search, scoped to the user."""
        self._execute(
            "DELETE FROM saved_searches WHERE id = %s AND user_id = %s",
            (search_id, user_id),
        )

    def update_alert_config(
        self,
        search_id: int,
        user_id: int,
        alert_enabled: bool,
        alert_level: str,
    ) -> None:
        """Update alert configuration for a saved search.

        Switching an alert on from off restarts its baseline at the current time,
        so only programmes that enter the index from now on count as new. In an
        SQL ``UPDATE`` every right-hand side reads the row as it was before the
        statement, so the CASE sees the *previous* ``alert_enabled`` value.
        Saving the form again with the alert already on leaves the baseline alone.

        Args:
            alert_level (str): One of ``shared.alert_levels.LEVELS``. The FastAPI
                alert job judges new programmes against it relative to the query.

        Raises:
            ValueError: If ``alert_level`` is not a known level.
        """
        if alert_level not in LEVELS:
            raise ValueError(f"Unknown alert level: {alert_level!r}")
        self._execute(
            """
            UPDATE saved_searches
            SET alert_baseline_at = CASE
                    WHEN alert_enabled = FALSE AND %s THEN NOW()
                    ELSE alert_baseline_at
                END,
                alert_enabled = %s,
                alert_level = %s,
                updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (
                alert_enabled,
                alert_enabled,
                alert_level,
                search_id,
                user_id,
            ),
        )
