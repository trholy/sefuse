"""Nightly Postgres housekeeping: expired sessions and the alert inbox.

Both tables grow on their own and nothing else prunes them — ``auth_sessions`` gains a
row per login, and ``alert_notifications`` is an append-only log. Neither is on a
request path, so both run from the cron lifespan.

Split out of ``main.py``. The retention window is a parameter rather than a module
constant read at call time: it lives in ``main.py``'s environment block, and reading a
caller's global from here is how a working late binding turns into a `NameError` at
05:00 rather than at import.

Each scheduled wrapper logs its own outcome and swallows the exception, because
housekeeping failing must not take down the job that runs after it. The underlying
functions raise, so a caller that wants to know can still tell.
"""

import logging

from .db import connection

logger = logging.getLogger(__name__)


def cleanup_expired_sessions() -> int:
    """Delete expired rows from ``auth_sessions``.

    Blocking DB work; call it from a thread or a scheduled job.

    Returns:
        int: Number of rows removed.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM auth_sessions WHERE expires_at < NOW()")
        return cur.rowcount


async def run_session_cleanup() -> None:
    """Scheduled job: remove expired sessions, logging success or failure."""
    try:
        removed = cleanup_expired_sessions()
        logger.info("Session cleanup completed, removed %d row(s)", removed)
    except Exception:
        logger.exception("Session cleanup failed")


def cleanup_old_alert_notifications(retention_days: int) -> int:
    """Delete in-app alert notifications older than ``retention_days``.

    Blocking DB work.

    Args:
        retention_days (int): Age in days beyond which a notification is pruned.

    Returns:
        int: Number of rows removed.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM alert_notifications
            WHERE created_at < NOW() - (%s * INTERVAL '1 day')
            """,
            (retention_days,),
        )
        return cur.rowcount


async def run_alert_notification_cleanup(retention_days: int) -> None:
    """Scheduled job: prune the in-app alert inbox, logging success or failure.

    Args:
        retention_days (int): Passed through to `cleanup_old_alert_notifications`.
            Supplied by the caller — see the module docstring.
    """
    try:
        removed = cleanup_old_alert_notifications(retention_days)
        logger.info(
            "Alert notification cleanup removed %d row(s) older than %d day(s)",
            removed,
            retention_days,
        )
    except Exception:
        logger.exception("Alert notification cleanup failed")
