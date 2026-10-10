"""Deployment-wide Gotify configuration, shared by FastAPI and Streamlit.

SeFuSe pushes alerts through a **single, operator-run Gotify server**. The
server URL lives in the environment and is never entered by users; what varies
per user is the *application token*, which is that user's private channel on the
shared server (see ``shared.secrets_box`` for how those are stored).

Configuration errors raise :class:`GotifyConfigError` rather than calling
``sys.exit`` directly, because the two services fail differently: FastAPI aborts
startup (``fastapi/src/main.py`` convention), while Streamlit surfaces the
problem in the page. Each service handles it at its own edge.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from .env import parse_bool

logger = logging.getLogger(__name__)

DEFAULT_PRIORITY = 5
DEFAULT_TIMEOUT_SECONDS = 10.0

# Gotify priorities are 0-10; anything outside that is a configuration mistake.
_MIN_PRIORITY = 0
_MAX_PRIORITY = 10


class GotifyConfigError(RuntimeError):
    """Raised when Gotify is enabled but misconfigured."""


@dataclass(frozen=True)
class GotifyConfig:
    """Resolved Gotify settings for this deployment.

    Attributes:
        enabled (bool): Master switch (``GOTIFY_ENABLED``). When False, every
            send path short-circuits and the settings page is hidden.
        base_url (str): Normalised base URL of the central server, without a
            trailing slash. Empty when disabled.
        priority (int): Default message priority (``GOTIFY_PRIORITY``).
        timeout (float): HTTP timeout in seconds for every Gotify call.
    """

    enabled: bool
    base_url: str
    priority: int
    timeout: float


def _read_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return bool(parse_bool(raw))


def _read_number(name: str, default: float, cast) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return cast(raw.strip())
    except ValueError as exc:
        raise GotifyConfigError(
            f"{name} must be a number, got {raw!r}"
        ) from exc


@lru_cache(maxsize=1)
def get_gotify_config() -> GotifyConfig:
    """Read and validate the Gotify environment once.

    Returns:
        GotifyConfig: Resolved settings. When ``GOTIFY_ENABLED`` is off the
        remaining fields are defaults and are never used.

    Raises:
        GotifyConfigError: When enabled but ``GOTIFY_URL`` is missing, is not a
            usable http(s) URL, or the priority/timeout values are unusable.
    """
    enabled = _read_bool("GOTIFY_ENABLED", False)
    priority = int(_read_number("GOTIFY_PRIORITY", DEFAULT_PRIORITY, int))
    timeout = _read_number(
        "GOTIFY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, float
    )

    if not enabled:
        return GotifyConfig(False, "", priority, timeout)

    if not _MIN_PRIORITY <= priority <= _MAX_PRIORITY:
        raise GotifyConfigError(
            f"GOTIFY_PRIORITY must be {_MIN_PRIORITY}-{_MAX_PRIORITY}, "
            f"got {priority}"
        )
    if timeout <= 0:
        raise GotifyConfigError(
            f"GOTIFY_TIMEOUT_SECONDS must be positive, got {timeout}"
        )

    raw_url = (os.getenv("GOTIFY_URL") or "").strip()
    if not raw_url:
        raise GotifyConfigError(
            "GOTIFY_ENABLED is true but GOTIFY_URL is not set"
        )

    # Imported here rather than at module scope: gotify.py imports this module
    # for its defaults, so a top-level import would be circular.
    from .gotify import is_allowed_gotify_url, normalize_server_url

    base_url = normalize_server_url(raw_url)
    if not is_allowed_gotify_url(base_url):
        raise GotifyConfigError(
            f"GOTIFY_URL is not a usable Gotify address: {raw_url!r}. "
            "It must be an http(s) URL naming your Gotify server."
        )

    return GotifyConfig(True, base_url, priority, timeout)


def push_enabled() -> bool:
    """Whether Gotify push is switched on *and* usable.

    ``ALERTS_ENABLED`` is checked first: push is a subset of the alert feature, so
    switching alerts off has to silence it here too, not only by leaving the nightly
    job unscheduled — an in-process caller reaches this either way.

    A misconfiguration is reported as "off" rather than raised. Both services want
    that: Streamlit would otherwise take every page down over a bad ``GOTIFY_URL``,
    and the alert run would rather deliver in-app notifications than nothing. FastAPI
    is the service that refuses to *start* on one, which is where that belongs. The
    error is logged either way, so an operator can still find it.

    Returns:
        bool: True when alerts are on and the Gotify config both loads and is enabled.
    """
    # Imported here rather than at module scope to keep this module importable in
    # contexts that only want the dataclass, matching the deferred gotify import above.
    from .alerts_config import alerts_enabled

    if not alerts_enabled():
        return False
    try:
        return get_gotify_config().enabled
    except GotifyConfigError:
        logger.error("Gotify is enabled but misconfigured; treating push as off",
                     exc_info=True)
        return False
