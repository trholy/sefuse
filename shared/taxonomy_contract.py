from __future__ import annotations

import re
import unicodedata
from typing import Iterable


TAXONOMY_FALLBACK_VALUE = "Unknown"
TAXONOMY_FALLBACK_KEY = "unknown"


def normalize_taxonomy_key(value: str | None) -> str:
    """Convert a raw taxonomy display value to a stable, ASCII lookup key.

    Applies lowercasing, umlaut expansion (ä→ae etc.), NFKD normalisation,
    whitespace/punctuation collapsing to underscores, and strips non-word chars.

    Args:
        value (str | None): Raw display value, e.g. `"Forschung & Entwicklung"`.

    Returns:
        str: Normalised key, e.g. `"forschung_entwicklung"`. Returns `""` for None.

    Example:
        normalize_taxonomy_key("Förderung") == "foerderung"
    """
    if value is None:
        return ""

    normalized = str(value).strip().lower()
    normalized = (
        normalized.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        c for c in normalized if not unicodedata.combining(c)
    )
    normalized = re.sub(r"[\s\-&/]+", "_", normalized)
    normalized = re.sub(r"[^\w]", "", normalized)
    return normalized.strip("_")


def is_invalid_taxonomy_value(value: str | None, key: str) -> bool:
    """Return True if a taxonomy value should be routed to the fallback bucket.

    A value is invalid when its normalised key is empty, null-like ("none", "nan", …),
    or shorter than three characters.

    Args:
        value (str | None): Original display value.
        key (str): Pre-computed normalised key from `normalize_taxonomy_key`.

    Returns:
        bool: True if the value should be treated as unknown/invalid.
    """
    if not key:
        return True

    text = str(value).strip().lower()
    if text in {"none", "nan", "", "null"}:
        return True

    if len(key) <= 2:
        return True

    return False


def score_taxonomy_display_value(value: str | None) -> int:
    """Score a display value for canonical-name selection (higher = preferred).

    Rewards mixed-case and spaced values; penalises all-lower or underscored ones.
    Used by `TaxonomyContractBuilder` to pick the best alias as the canonical label.

    Args:
        value (str | None): Display string to score.

    Returns:
        int: Relative score; -1 for None.
    """
    if value is None:
        return -1

    text = str(value)
    score = 0

    if any(c.isupper() for c in text):
        score += 2
    if " " in text:
        score += 2
    if "_" in text:
        score -= 1
    if text.islower():
        score -= 1

    return score


def taxonomy_key_set(values: Iterable[object] | None) -> set[str]:
    """Convert an iterable of raw taxonomy values to a set of normalised keys.

    Used by both FastAPI (filter matching) and Streamlit (sidebar filter comparison)
    to ensure consistent key normalisation across services.

    Args:
        values (Iterable[object] | None): Raw taxonomy strings or mixed types.
            None and empty strings are silently skipped.

    Returns:
        set[str]: Set of normalised keys produced by `normalize_taxonomy_key`.

    Example:
        taxonomy_key_set(["Zuschuss", "Darlehen"]) == {"zuschuss", "darlehen"}
    """
    if values is None:
        return set()

    keys: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        keys.add(normalize_taxonomy_key(text))
    return keys
