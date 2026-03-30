from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import AuthSettings


class Database:
    def __init__(self, settings: AuthSettings):
        self._settings = settings

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
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

    @contextmanager
    def dict_cursor(self) -> Iterator[RealDictCursor]:
        with self.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor

