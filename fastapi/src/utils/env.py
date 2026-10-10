"""Environment-variable parsing helpers with fail-fast validation.

Centralises the bool/int/hour coercion that was previously duplicated across
``main.py`` (inline truthy-sets and ``_read_cron_hour``). On invalid values the
int/hour helpers log a critical message and exit the process, matching
FastAPI's startup fail-fast convention.
"""

import logging
import os
import sys

from shared.env import parse_bool

logger = logging.getLogger(__name__)


def read_bool(name: str, default: bool = False) -> bool:
    """Read an env var as a boolean.

    Vocabulary comes from ``shared.env.parse_bool``. An unset var returns
    ``default``; a value that is set but unreadable is treated as False rather than
    raising, which is what every caller of this helper wants — these are tuning
    knobs, and FastAPI already fails fast on the secrets that matter.

    Args:
        name (str): Environment variable name.
        default (bool): Value to return when the variable is unset.

    Returns:
        bool: Parsed boolean value.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return bool(parse_bool(raw))


def read_int(name: str, default: int) -> int:
    """Read an env var as an integer, exiting on a non-integer value.

    Args:
        name (str): Environment variable name.
        default (int): Value to use when the variable is unset.

    Returns:
        int: Parsed integer value.
    """
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.critical("Invalid integer value for %s: %s", name, raw)
        sys.exit(1)


def read_hour(name: str, default: int) -> int:
    """Read an env var as a cron hour-of-day (0-23), exiting on invalid values.

    Args:
        name (str): Environment variable name.
        default (int): Hour to use when the variable is unset.

    Returns:
        int: Validated hour in the range 0-23.
    """
    value = read_int(name, default)
    if not 0 <= value <= 23:
        logger.critical("%s must be in range 0-23, got %d", name, value)
        sys.exit(1)
    return value
