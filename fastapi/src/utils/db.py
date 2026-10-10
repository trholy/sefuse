"""Shared PostgreSQL connection factory for FastAPI-side database access.

The FastAPI service only touches Postgres from infrequent daily cron jobs
(the saved-search alert check and the expired-session cleanup), so a single
open-and-close connection per run is sufficient — no pool is needed here.
This factory removes the duplicated ``psycopg2.connect(...)`` blocks that were
previously hand-rolled in ``main.py`` and ``alert_service.py``.

``connection()`` is boilerplate removal on top of that factory and is explicitly
**not** a step toward pooling: it owns one connection's lifetime, nothing more.
Streamlit pools (``streamlit/src/auth/db.py``) because it serves interactive
requests; this service opens a handful of connections a day.
"""

import logging
import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2

logger = logging.getLogger(__name__)


@contextmanager
def connection() -> Iterator["psycopg2.extensions.connection"]:
    """Open a connection, commit on clean exit, roll back on error, always close.

    Replaces the open/try/finally-close/except block that every function in
    ``first_seen.py`` used to hand-roll.

    Unlike ``streamlit/src/auth/db.py``, the rollback and close are each guarded.
    A bare ``except Exception: conn.rollback(); raise`` loses the original
    diagnostic whenever the socket is already gone, because ``rollback()`` then
    raises ``InterfaceError`` from inside the handler and *that* is what
    propagates — so the caller sees "connection already closed" instead of the
    error that closed it.

    Yields:
        psycopg2 connection: Open connection, owned by this context manager.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            logger.debug("Rollback failed; the connection was already lost",
                         exc_info=True)
        raise
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Closing the connection failed", exc_info=True)


def get_connection():
    """Open a new psycopg2 connection using the ``DB_*`` environment variables.

    Returns:
        psycopg2 connection. Callers are responsible for closing it (or using it
        as a context manager).
    """
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "sefuse"),
        user=os.getenv("DB_USER", "sefuse"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
    )
