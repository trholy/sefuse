"""Environment-value parsing shared by both services.

Only the *parsing* lives here, never the policy. The four places that read booleans
from the environment disagree on purpose about what to do with a value they cannot
read, and that disagreement is correct:

- ``fastapi/src/utils/env.py`` and ``shared/gotify_config.py`` fall back to the
  caller's default,
- ``shared/alerts_config.py`` treats anything unrecognised as "off", because a
  master switch that fails open is worse than one that fails closed,
- ``streamlit/src/auth/config.py`` raises ``ConfigurationError``, because a typo in
  ``AUTH_ENABLED`` must not quietly leave a deployment unauthenticated.

Merging those into one helper would mean picking one policy for all four. So the
truthy/falsy vocabulary is shared and each caller keeps its own reaction to
`None` — the same split `shared.alert_levels` uses for level names versus the
rules behind them.

This module deliberately imports nothing beyond the standard library, so it stays
importable in any context either container can reach.
"""

from __future__ import annotations

#: Accepted spellings, lowercased and stripped before lookup. Kept as the union of
#: what the four previous copies accepted, so no deployment's .env changes meaning.
TRUTHY = frozenset({"1", "true", "yes", "on"})
FALSY = frozenset({"0", "false", "no", "off"})


def parse_bool(raw: str | None) -> bool | None:
    """Parse an environment value as a boolean.

    Args:
        raw (str | None): Raw value as read from the environment, or ``None`` when
            the variable is unset.

    Returns:
        bool | None: ``True`` or ``False`` for a recognised spelling. ``None`` when
            there is nothing to parse — either the variable was unset, or it holds
            text that is not a boolean at all.

    Note:
        ``None`` covers both "unset" and "unreadable", which most callers need to
        tell apart: an unset variable takes their default, while an unreadable one
        is a configuration mistake. Check ``raw is None`` first when the two differ
        for you, and only then ask this function what the text means.
    """
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in TRUTHY:
        return True
    if value in FALSY:
        return False
    return None
