"""Alert service that checks saved search alerts and sends notifications."""

import logging
from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor

from shared.alerts_config import alerts_enabled
from shared.gotify import GotifyClient
from shared.gotify_config import push_enabled
from shared.secrets_box import decrypt

from .db import get_connection
from .first_seen import fetch_new_since
from .match_levels import judge

logger = logging.getLogger(__name__)

# Notification title. Kept short and constant so a phone's notification list
# groups SeFuSe alerts together; the interesting content is in the body.
NOTIFICATION_TITLE = "SeFuSe"

# Upper bound on messages pushed for a single alert in one run. The first run of
# a broad saved search can match hundreds of programmes, and one push per
# programme would flood the user's device; the remainder is summarised instead.
MAX_MESSAGES_PER_ALERT = 20

_COLLECTION_LABELS = {"german": "German", "eu": "EU"}


def _format_match_message(match: dict, search_title: str, source: str) -> str:
    """Build the one-line body for a single newly matched programme.

    The programme name is emitted as a markdown link so Gotify clients render
    it as tappable; without a website we fall back to the bare title rather
    than producing an empty link.
    """
    name = match.get("project_title") or "Untitled"
    website = match.get("project_website") or ""
    label = f"[{name}]({website})" if website else name
    return (
        f'funding alert — "{label}" from {source} '
        f'matches your search "{search_title}"'
    )


class AlertService:
    """Checks saved search alerts against newly indexed programmes and notifies.

    An alert does not re-run its search over the whole index. It takes the
    programmes first seen since the alert was switched on and scores only those
    against the saved query, so a new programme never has to outrank every existing
    one to be noticed. Whether a scored programme is good enough is judged relative
    to the query itself (see :mod:`utils.match_levels`).

    Args:
        score_fn: Async callable ``(query_text, collection_type, filters,
            candidate_ids) -> (matches, stats)``. ``matches`` are result dicts
            (``project_id``, ``project_title``, ``project_website``,
            ``dense_score`` …) for the candidates that pass the saved filters, and
            ``stats`` is the query's :class:`~utils.match_levels.QueryStats`: its
            ranking of the existing programmes (candidates excluded) and the
            collection's noise floor.
    """

    def __init__(self, score_fn):
        self._score_fn = score_fn

    async def check_all_alerts(self) -> int:
        """Check all active alerts and send notifications for new matches.

        Returns:
            Number of alerts that found new matches.
        """
        if not alerts_enabled():
            logger.info("ALERTS_ENABLED is false — skipping alert check")
            return 0

        conn = get_connection()
        try:
            alerts = self._load_active_alerts(conn)
            logger.info("Checking %d active alert(s)", len(alerts))
            triggered = 0

            for alert in alerts:
                try:
                    new_matches = await self._check_single_alert(alert, conn)
                    if new_matches:
                        triggered += 1
                except Exception:
                    logger.exception("Failed to check alert id=%s", alert["id"])
        finally:
            conn.close()

        return triggered

    def _load_active_alerts(self, conn) -> list[dict]:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.id, s.user_id, s.title, s.query_text, s.collection_type,
                       s.filters, s.alert_level, s.alert_known_project_ids,
                       s.alert_baseline_at, u.gotify_token
                FROM saved_searches s
                JOIN auth_users u ON u.id = s.user_id
                WHERE s.alert_enabled = TRUE
                """
            )
            return list(cur.fetchall())

    async def _check_single_alert(self, alert: dict, conn) -> list[dict]:
        known_ids = set(alert["alert_known_project_ids"] or [])
        new_matches = await self._select_new_matches(alert, known_ids)

        notified_ids: list[str] = []
        if new_matches:
            self._insert_in_app_notifications(alert, new_matches, conn)
            token = self._push_token(alert)
            if token:
                notified_ids = self._send_notification(alert, new_matches, token)
            else:
                # No push channel for this user — Gotify is switched off, or
                # they have not set a token. The in-app inbox is then the only
                # delivery and it has just succeeded, so treat every match as
                # notified. Returning [] here instead would re-insert the same
                # inbox rows on every subsequent run.
                notified_ids = [r.get("project_id", "") for r in new_matches]

        # The known set only ever grows, and only with programmes whose
        # notification succeeded, so a programme is never announced twice.
        all_known_ids = list(dict.fromkeys([*known_ids, *notified_ids]))
        self._update_alert_state(alert["id"], all_known_ids, conn)

        return new_matches

    async def _select_new_matches(self, alert: dict, known_ids: set[str]) -> list[dict]:
        """Score the programmes new since the alert began and keep those that pass.

        Candidates are the programmes first seen after ``alert_baseline_at`` that
        are not near-duplicates of an older one and have not been notified yet.
        With none, the query is not even embedded. Each scored candidate is judged
        against the alert's level; passing matches carry the ``rank`` they were
        judged on and come back best first.
        """
        candidates = [
            pid
            for pid in fetch_new_since(alert["collection_type"], alert["alert_baseline_at"])
            if pid not in known_ids
        ]
        if not candidates:
            return []

        matches, stats = await self._score_fn(
            query_text=alert["query_text"],
            collection_type=alert["collection_type"],
            filters=alert["filters"] if isinstance(alert["filters"], dict) else {},
            candidate_ids=candidates,
        )

        passed = []
        for match in matches:
            if match.get("dense_score") is None:
                continue
            verdict = judge(alert["alert_level"], match["dense_score"], stats)
            logger.debug(
                "Alert id=%s: %s cosine=%.3f rank=%d floor=%.3f level=%s -> %s",
                alert["id"], match.get("project_id"), match["dense_score"],
                verdict.rank, stats.noise_floor, alert["alert_level"], verdict.passed,
            )
            if verdict.passed:
                passed.append({**match, "rank": verdict.rank})

        passed.sort(key=lambda m: m["dense_score"], reverse=True)
        logger.info(
            "Alert id=%s: %d candidate(s), %d scored, %d passed level %s",
            alert["id"], len(candidates), len(matches), len(passed), alert["alert_level"],
        )
        return passed

    def _push_token(self, alert: dict) -> str:
        """The user's decrypted Gotify token, or ``""`` when push is unavailable.

        Empty means there is no push channel at all — either the feature is off
        deployment-wide or this user has not configured a token — as opposed to
        a push that was attempted and failed. ``_check_single_alert`` relies on
        that distinction to decide whether an unsent match should be retried.
        """
        if not push_enabled():
            logger.debug(
                "Alert id=%s: Gotify disabled, in-app notification only",
                alert["id"],
            )
            return ""
        token = decrypt(alert.get("gotify_token") or "")
        if not token:
            logger.warning(
                "Alert id=%s: user has no Gotify token configured", alert["id"]
            )
        return token

    def _send_notification(
        self, alert: dict, new_matches: list[dict], token: str
    ) -> list[str]:
        """Push one Gotify message per newly matched programme.

        Sends to the user's own channel on the central server, identified by
        their application token.

        Args:
            alert (dict): The saved-search row being checked.
            new_matches (list[dict]): Matches not yet notified.
            token (str): The user's decrypted Gotify token, from
                :meth:`_push_token`.

        Returns:
            list[str]: The ``project_id`` of every match that was pushed
            successfully. Anything omitted stays out of
            ``alert_known_project_ids`` and is retried on the next run, so a
            transient Gotify outage never silently swallows a match.
        """
        source = _COLLECTION_LABELS.get(
            alert["collection_type"], alert["collection_type"]
        )
        client = GotifyClient(token)

        notified: list[str] = []
        for match in new_matches[:MAX_MESSAGES_PER_ALERT]:
            body = _format_match_message(match, alert["title"], source)
            if client.send(NOTIFICATION_TITLE, body):
                notified.append(match.get("project_id", ""))

        overflow = len(new_matches) - MAX_MESSAGES_PER_ALERT
        if overflow > 0 and notified:
            # Best-effort: the summary is informational, so its success does not
            # affect which project IDs are marked as notified.
            client.send(
                NOTIFICATION_TITLE,
                f'…and {overflow} more programme(s) matching your search '
                f'"{alert["title"]}". Open SeFuSe to see them all.',
            )

        logger.info(
            "Alert id=%s: pushed %d of %d new match(es)",
            alert["id"],
            len(notified),
            len(new_matches),
        )
        return notified

    def _insert_in_app_notifications(
        self, alert: dict, new_matches: list[dict], conn
    ) -> None:
        rows = [
            (
                alert["user_id"],
                alert["id"],
                match.get("project_id", ""),
                match.get("project_title", ""),
                match.get("project_website", ""),
                # A raw cosine. The column is named matching_score for historical
                # reasons (migration 002) and is kept for diagnostics; it is not a
                # percentage and the inbox no longer renders it as one.
                match.get("dense_score", 0),
            )
            for match in new_matches
        ]
        try:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO alert_notifications
                        (user_id, saved_search_id, project_id,
                         project_title, project_website, matching_score)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
            conn.commit()
        except Exception:
            logger.exception(
                "Failed to insert in-app notifications for alert id=%s",
                alert["id"],
            )

    def _update_alert_state(
        self, alert_id: int, known_project_ids: list[str], conn
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE saved_searches
                SET alert_known_project_ids = %s,
                    alert_last_run = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (known_project_ids, datetime.now(timezone.utc), alert_id),
            )
        conn.commit()
