from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from .config import AuthSettings


class Database:
    """psycopg2 connection pool backed by ``ThreadedConnectionPool``.

    Connections are acquired from the pool on each ``connection()`` call,
    committed (or rolled back on error), and returned to the pool in the
    ``finally`` block — no new TCP connections are opened per request.

    Args:
        settings (AuthSettings): Frozen dataclass with DB host, port, credentials, and timeout.

    Example:
        db = Database(settings)
        with db.connection() as conn:
            conn.cursor().execute("SELECT 1")
        db.close()
    """

    def __init__(self, settings: AuthSettings):
        """Initialise the connection pool with the given auth settings.

        Args:
            settings (AuthSettings): Frozen dataclass with DB host, port, credentials, and timeout.
        """
        self._settings = settings
        self._pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connect_timeout=settings.db_connect_timeout_seconds,
        )

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Acquire a connection from the pool, yield it, and return it on exit.

        Commits on clean exit, rolls back on exception, and always returns the
        connection to the pool via ``putconn``.

        Yields:
            psycopg2.extensions.connection: Pooled database connection.
        """
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        """Close all connections in the pool."""
        self._pool.closeall()
