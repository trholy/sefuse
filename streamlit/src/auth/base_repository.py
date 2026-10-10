"""Shared base class for all psycopg2-backed repository classes."""

from psycopg2.extras import RealDictCursor

from .db import Database


class BaseRepository:
    """Common infrastructure for PostgreSQL-backed repositories.

    Provides a ``_execute`` helper that opens a connection from ``Database``,
    runs a parameterised query, and returns rows (or ``None`` for write
    operations).  Callers that need multiple queries inside one transaction
    should use ``self._database.connection()`` directly.

    Args:
        database (Database): Connection pool factory.
    """

    def __init__(self, database: Database):
        """Initialise the repository with a connection pool factory.

        Args:
            database (Database): Connection pool factory used for all queries.
        """
        self._database = database

    def _execute(
        self,
        query: str,
        params=None,
        *,
        fetch: bool = False,
        fetchone: bool = False,
    ):
        """Execute a SQL query and optionally return rows.

        Opens a connection from the pool, runs the query with ``params``, and
        commits on success (the pool's context manager handles commit/rollback).
        Returns rows when ``fetch`` or ``fetchone`` is ``True``; returns
        ``None`` for write operations.

        Args:
            query (str): Parameterised SQL statement.
            params: Sequence or mapping of bind parameters (default ``None``).
            fetch (bool): If ``True``, return all rows as a list of dicts.
            fetchone (bool): If ``True``, return the first row as a dict (or
                ``None`` if no row matched).

        Returns:
            list[dict] | dict | None: Rows when ``fetch`` or ``fetchone`` is
            set; ``None`` for write queries.
        """
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetchone:
                    return cur.fetchone()
                if fetch:
                    return cur.fetchall()
                conn.commit()
                return None
