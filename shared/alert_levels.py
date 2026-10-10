"""Names of the saved-search alert match levels.

Shared so the Streamlit UI (which lets a user pick a level) and the FastAPI alert
job (which judges new programmes against it) cannot drift apart. Only the names and
labels live here; the rule behind each name (rank among the query's top k existing
programmes, plus a per-collection noise floor) lives in the FastAPI service.
"""

# Ordered from most to least permissive.
LEVELS: tuple[str, ...] = ("broad", "balanced", "strict")
DEFAULT_LEVEL = "balanced"

LEVEL_LABELS: dict[str, str] = {
    "broad": "Broad - among your top 25",
    "balanced": "Balanced - top 10",
    "strict": "Strict - top 3",
}


def normalize_level(value: object) -> str:
    """Return ``value`` if it names a level, otherwise :data:`DEFAULT_LEVEL`.

    Args:
        value (object): Candidate level name, e.g. from a database row.

    Returns:
        str: One of :data:`LEVELS`.
    """
    return value if isinstance(value, str) and value in LEVELS else DEFAULT_LEVEL
