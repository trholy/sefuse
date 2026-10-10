"""Deployment-wide master switch for saved-search alerts, shared by both services.

``ALERTS_ENABLED`` is a level above ``GOTIFY_ENABLED``: that one turns off *push*
delivery while the alert machinery keeps running, this one turns off the feature
entirely — the nightly check job, the in-app inbox, the sidebar badge and every
alert control in the UI.

It lives in ``shared/`` rather than in either service's own env helper because
FastAPI and Streamlit both read it and neither one's parser
(``fastapi/src/utils/env.py``, ``streamlit/src/auth/config.py``) is importable
from the other container.

Unlike ``shared.gotify_config``, there is nothing here that can be
*mis*configured: an unrecognised value reads as off rather than raising, and an
unset variable defaults to on so existing deployments are unchanged.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .env import parse_bool


@lru_cache(maxsize=1)
def alerts_enabled() -> bool:
    """Return True when saved-search alerts are switched on for this deployment.

    Returns:
        bool: ``True`` when ``ALERTS_ENABLED`` is unset or truthy (``1``, ``true``,
        ``yes``, ``on``, case-insensitive), ``False`` for any other set value.
    """
    raw = os.getenv("ALERTS_ENABLED")
    if raw is None:
        return True
    return bool(parse_bool(raw))
