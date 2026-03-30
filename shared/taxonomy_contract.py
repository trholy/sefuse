from __future__ import annotations

import re
import unicodedata
from typing import Iterable


TAXONOMY_FALLBACK_VALUE = "Unknown"
TAXONOMY_FALLBACK_KEY = "unknown"


def normalize_taxonomy_key(value: str | None) -> str:
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
    if not key:
        return True

    text = str(value).strip().lower()
    if text in {"none", "nan", "", "null"}:
        return True

    if len(key) <= 2:
        return True

    return False


def score_taxonomy_display_value(value: str | None) -> int:
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
