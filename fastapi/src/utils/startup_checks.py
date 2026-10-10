"""Security-critical environment validation, run once before the app is built.

These checks call ``sys.exit(1)`` rather than raising: a half-configured deployment
must not start at all. A placeholder ``INTERNAL_API_TOKEN`` would leave the internal
API open; a half-configured Gotify is worse than none, because alerts would silently
stop reaching users while everything still looked healthy.

Everything happens inside :func:`validate_startup` — this module has **no** import-time
side effects. That matters for more than tidiness: the test harness loads modules
before it seeds the environment, so a top-level ``sys.exit`` here would fire at
whatever point the module happened to be imported, rather than where the caller
intends it.

``main.py`` keeps the resulting values as its own module attributes, because the
middleware reads the token from there and tests monkeypatch it there.
"""

import logging
import os
import sys
from dataclasses import dataclass
from typing import NoReturn

from shared.alerts_config import alerts_enabled
from shared.gotify_config import GotifyConfig, GotifyConfigError, get_gotify_config
from shared.secrets_box import SecretKeyError, ensure_key_available

from .env import read_bool

logger = logging.getLogger(__name__)

#: Inner width of the failure banner, wide enough for the longest line it carries.
_BOX_WIDTH = 66

#: Every secret in .env.example ships with this prefix, so a value that still starts
#: with it means the operator has not replaced it.
PLACEHOLDER_PREFIX = "change_me"


@dataclass(frozen=True)
class StartupConfig:
    """What the startup checks resolved, for the app to hold onto.

    Attributes:
        internal_api_token (str): Shared secret for the internal API. Empty only when
            the unauthenticated bypass is explicitly enabled.
        alerts_enabled (bool): Master switch for the saved-search alert feature.
        gotify (GotifyConfig): Resolved Gotify settings. Disabled defaults when alerts
            are off, so no caller has to special-case that.
    """

    internal_api_token: str
    alerts_enabled: bool
    gotify: GotifyConfig


def _fail_startup(title: str, *body_lines: str) -> NoReturn:
    """Log a boxed failure banner and exit the process.

    The banner exists because this is the error an operator hits on their first run,
    in a wall of container logs — it has to be impossible to scroll past. Rendering it
    here rather than writing it out per call site keeps the width consistent, which
    hand-maintained copies of it were not.

    Args:
        title (str): One-line reason, shown as "STARTUP FAILED: <title>".
        *body_lines (str): What the operator should do. An empty string is a spacer.

    Raises:
        SystemExit: Always, with status 1.
    """
    edge = "═" * _BOX_WIDTH
    lines = [f"STARTUP FAILED: {title}", ""] + list(body_lines)
    boxed = "\n".join(f"║ {line:<{_BOX_WIDTH - 2}} ║" for line in lines)
    logger.critical("\n╔%s╗\n%s\n╚%s╝", edge, boxed, edge)
    sys.exit(1)


def _check_internal_api_token() -> str:
    """Return the internal API token, or exit when it is missing or a placeholder."""
    token = os.getenv("INTERNAL_API_TOKEN", "")

    if not token:
        if read_bool("ALLOW_UNAUTHENTICATED_INTERNAL_API"):
            logger.warning("FastAPI is running without internal token authentication")
            return token
        _fail_startup(
            "INTERNAL_API_TOKEN is not set",
            "Before running docker-compose, set up your .env file:",
            "  1. cp .env.example .env",
            "  2. Replace all change_me_* values with real secrets",
            "",
            "For local development without a token:",
            "  Add ALLOW_UNAUTHENTICATED_INTERNAL_API=true to .env",
            "",
            "See README.md → Security Notes for details.",
        )

    # Independent of the QDRANT_API_KEY check: this must run whether or not Qdrant
    # auth is configured, or a placeholder token could boot on a deployment that
    # simply left QDRANT_API_KEY unset.
    if token.startswith(PLACEHOLDER_PREFIX):
        _fail_startup(
            "INTERNAL_API_TOKEN still uses a placeholder",
            "Edit .env and replace the change_me_* value with a real secret.",
            "See README.md → Security Notes for details.",
        )
    return token


def _check_qdrant_api_key() -> None:
    """Warn when Qdrant auth is off; exit when its key is still a placeholder."""
    key = os.getenv("QDRANT_API_KEY", "")
    if not key:
        logger.warning(
            "QDRANT_API_KEY is not set — Qdrant is running without authentication. "
            "Set QDRANT_API_KEY in .env for production deployments."
        )
        return
    if key.startswith(PLACEHOLDER_PREFIX):
        _fail_startup(
            "QDRANT_API_KEY still uses a placeholder",
            "Edit .env and replace the change_me_* value with a real secret.",
        )


def _check_gotify(alerts_on: bool) -> GotifyConfig:
    """Resolve the Gotify config, or exit when it is enabled but unusable.

    When alerts are switched off the Gotify environment is not read at all, so a
    stale ``GOTIFY_URL`` cannot hold back a deployment that does not use alerts.
    """
    if not alerts_on:
        return GotifyConfig(False, "", 0, 0.0)
    try:
        config = get_gotify_config()
        if config.enabled:
            # Fail here rather than at the first push: a missing Fernet key means
            # every stored token is unreadable, and the failure would otherwise
            # surface at 05:00 as alerts that simply never arrive.
            ensure_key_available()
        return config
    except (GotifyConfigError, SecretKeyError) as exc:
        _fail_startup(
            str(exc),
            "Gotify is enabled but misconfigured. Fix it, or set",
            "GOTIFY_ENABLED=false (or ALERTS_ENABLED=false) in .env.",
        )


def validate_startup() -> StartupConfig:
    """Validate the security-critical environment, or abort the process.

    Returns:
        StartupConfig: The resolved values for the app to hold onto.

    Raises:
        SystemExit: With status 1, on any unusable configuration.
    """
    token = _check_internal_api_token()
    _check_qdrant_api_key()
    alerts_on = alerts_enabled()
    return StartupConfig(
        internal_api_token=token,
        alerts_enabled=alerts_on,
        gotify=_check_gotify(alerts_on),
    )
