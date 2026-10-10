"""Persistent record of when each programme first entered the index.

Saved-search alerts use this to tell a genuinely new programme from one that
merely moved into a search's top results. See ``streamlit/migrations/
005_alert_first_seen.sql`` for why it is a Postgres table rather than a Qdrant
payload key.

Every function here fails soft: an unreachable database is logged and reported as
"nothing recorded / nothing known" instead of raising, because the embedding
pipeline must never be blocked by it. The consequence is deliberately one-sided —
a programme that fails to be stamped can miss an alert, but can never trigger a
false one, because a programme with no row is treated as not new.
"""

import logging
from datetime import datetime, timezone
from typing import Sequence

from .db import connection

logger = logging.getLogger(__name__)

# Stamp for programmes that were already indexed before first-seen tracking
# existed. Older than any alert baseline, so they never count as new.
LEGACY_FIRST_SEEN = datetime(1970, 1, 1, tzinfo=timezone.utc)


def fetch_known_ids(collection_type: str, project_ids: list[str]) -> set[str]:
    """Return the subset of ``project_ids`` that already has a first-seen row.

    Args:
        collection_type (str): ``"german"`` or ``"eu"``.
        project_ids (list[str]): Candidate project UUIDs.

    Returns:
        set[str]: Ids with a row. Empty on an empty input or a database error.
    """
    if not project_ids:
        return set()
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT project_id FROM programme_first_seen "
                "WHERE collection_type = %s AND project_id = ANY(%s)",
                (collection_type, list(project_ids)),
            )
            return {row[0] for row in cur.fetchall()}
    except Exception:
        logger.exception("Could not read programme_first_seen (%s)", collection_type)
        return set()


def record_first_seen(
    collection_type: str,
    ids_now: Sequence[str] = (),
    ids_legacy: Sequence[str] = (),
) -> None:
    """Stamp programmes that have no first-seen row yet.

    Existing rows are never touched (``ON CONFLICT DO NOTHING``), so a programme
    that is deleted and later re-inserted keeps its original time.

    Args:
        collection_type (str): ``"german"`` or ``"eu"``.
        ids_now (list[str]): Programmes first seen right now — a genuine insert.
        ids_legacy (list[str]): Programmes already indexed before tracking
            existed; stamped with :data:`LEGACY_FIRST_SEEN` so they never alert.
    """
    now = datetime.now(timezone.utc)
    rows = [(collection_type, pid, now) for pid in ids_now]
    rows += [(collection_type, pid, LEGACY_FIRST_SEEN) for pid in ids_legacy]
    if not rows:
        return
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO programme_first_seen "
                "(collection_type, project_id, first_seen_at) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                rows,
            )
    except Exception:
        logger.exception("Could not write programme_first_seen (%s)", collection_type)


def fetch_new_since(collection_type: str, since: datetime) -> list[str]:
    """Return programmes first seen after ``since`` that are not near-duplicates.

    This is the candidate set of a saved-search alert: only these programmes are
    scored against its query, so a new programme never has to outrank the whole
    index to be noticed.

    Args:
        collection_type (str): ``"german"`` or ``"eu"``.
        since (datetime): The alert's baseline.

    Returns:
        list[str]: Project ids, oldest first. Empty on a database error.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT project_id FROM programme_first_seen "
                "WHERE collection_type = %s AND first_seen_at > %s "
                "AND duplicate_of IS NULL "
                "ORDER BY first_seen_at, project_id",
                (collection_type, since),
            )
            return [row[0] for row in cur.fetchall()]
    except Exception:
        logger.exception("Could not read programme_first_seen (%s)", collection_type)
        return []


def mark_duplicates(
    collection_type: str,
    pairs: Sequence[tuple[str, str]],
) -> None:
    """Record that each newly seen programme is a near-copy of an older one.

    Such programmes are excluded from :func:`fetch_new_since`, so they cannot alert
    as "new".

    One statement for the whole run, rather than one per duplicate: the check walks
    every newly stamped programme, and the first run after a re-index opens hundreds
    of them. A failure is logged and swallowed, at a cost of at most one duplicate
    alert per pair.

    The write is all-or-nothing, where per-duplicate commits were not. That widens
    the blast radius on paper, but the realistic failure here is "the database is
    unreachable", which lost every mark anyway.

    Args:
        collection_type (str): ``"german"`` or ``"eu"``.
        pairs (Sequence[tuple[str, str]]): ``(project_id, duplicate_of)`` for each
            near-duplicate found this run.
    """
    if not pairs:
        return
    rows = [(duplicate_of, collection_type, pid) for pid, duplicate_of in pairs]
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.executemany(
                "UPDATE programme_first_seen SET duplicate_of = %s "
                "WHERE collection_type = %s AND project_id = %s",
                rows,
            )
    except Exception:
        logger.exception(
            "Could not mark %d duplicate(s) in programme_first_seen (%s)",
            len(rows), collection_type,
        )


def delete_first_seen(collection_type: str, project_ids: list[str]) -> None:
    """Remove first-seen rows. Used by test tooling to re-arm a fixture."""
    if not project_ids:
        return
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM programme_first_seen "
                "WHERE collection_type = %s AND project_id = ANY(%s)",
                (collection_type, list(project_ids)),
            )
    except Exception:
        logger.exception("Could not delete programme_first_seen (%s)", collection_type)
