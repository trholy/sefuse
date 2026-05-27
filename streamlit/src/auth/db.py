from contextlib import contextmanager
from typing import Iterator

import psycopg2

from .config import AuthSettings


class Database:
    """Thin psycopg2 connection factory that reads credentials from `AuthSettings`.

    Args:
        settings (AuthSettings): Frozen dataclass with DB host, port, credentials, and timeout.

    Example:
        db = Database(settings)
        with db.connection() as conn:
            conn.cursor().execute("SELECT 1")
    """

    def __init__(self, settings: AuthSettings):
        """Initialise the connection factory with the given auth settings.

        Args:
            settings (AuthSettings): Frozen dataclass with DB host, port, credentials, and timeout.
        """
        self._settings = settings

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Open a psycopg2 connection, yield it, and close it on exit.

        Yields:
            psycopg2.extensions.connection: Open database connection.
        """
        connection = psycopg2.connect(
            host=self._settings.db_host,
            port=self._settings.db_port,
            dbname=self._settings.db_name,
            user=self._settings.db_user,
            password=self._settings.db_password,
            connect_timeout=self._settings.db_connect_timeout_seconds,
        )
        try:
            yield connection
        finally:
            connection.close()


