import os
from typing import List, Any, Union, Dict
import logging
from datetime import datetime

import requests
import streamlit as st

logger = logging.getLogger(__name__)

_INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")


def _api_headers() -> dict[str, str]:
    """Build HTTP headers for internal FastAPI requests.

    Includes the ``X-Internal-Token`` header when the
    ``INTERNAL_API_TOKEN`` environment variable is set, allowing the
    FastAPI ``InternalTokenMiddleware`` to authenticate the caller.

    Returns:
        dict[str, str]: Header dict (may be empty if no token is configured).
    """
    headers: dict[str, str] = {}
    if _INTERNAL_API_TOKEN:
        headers["X-Internal-Token"] = _INTERNAL_API_TOKEN
    return headers


def safe_join(
        value: Union[List[Any], None],
        sep: str = ", ",
        default: str = "N/A"
) -> str:
    """Join a list to a display string, returning a default for empty or None input.

    Args:
        value (List[Any] | None): List of values to join, or None.
        sep (str, default=", "): Separator placed between items.
        default (str, default="N/A"): Returned when `value` is empty or None.

    Returns:
        str: Joined string or the default value.
    """
    if not value:
        return default
    if isinstance(value, (list, tuple, set)):
        return sep.join(str(v) for v in value if v is not None)
    return str(value)


def search_projects(
        fastapi_url: str,
        model: str,
        query: str,
        search_limit: int,
        endpoint: str,
        semantic_weight: float = 0.7,
        filters: Dict[str, List[str]] | None = None,
        timeout: int = 30
) -> tuple[List[Dict], bool]:
    """Send a search request to the FastAPI backend and return the matched projects.

    Args:
        fastapi_url (str): Base URL of the FastAPI service, e.g. `"http://fastapi:8000"`.
        model (str): Embedding model name forwarded in the request body.
        query (str): User's natural-language search text.
        search_limit (int): Maximum number of results to request.
        endpoint (str): API path, e.g. `"/v1/search/german"`.
        semantic_weight (float, default=0.7): Hybrid search weight (0=keyword, 1=semantic).
        filters (Dict[str, List[str]] | None, default=None): Optional taxonomy filters
            and drop_na flag forwarded to the backend.
        timeout (int, default=30): HTTP request timeout in seconds.

    Returns:
        tuple[List[Dict], bool]: The project dicts from the `matches` key, and the
            response's `weak_match` flag — True when nothing in the collection is a
            genuinely relevant match for the query. The flag is needed because each
            match's `relative_score` is relative to the best hit in the response, so
            the top result always reads 100% even for an off-topic query.

    Raises:
        requests.HTTPError: On non-2xx responses.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "limit": search_limit,
        "semantic_weight": semantic_weight,
    }
    if filters:
        payload["filters"] = filters

    response = requests.post(
        f"{fastapi_url}{endpoint}",
        json=payload,
        headers=_api_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("matches", []), bool(data.get("weak_match", False))


@st.cache_data(ttl=300)
def fetch_german_taxonomy(
        fastapi_url: str,
        timeout: int = 30
) -> Dict[str, Any]:
    """Fetch the German taxonomy artifact from the FastAPI `/v1/vocab/german` endpoint.

    Result is cached by Streamlit for 300 seconds to avoid redundant API calls
    on every sidebar re-render.

    Args:
        fastapi_url (str): Base URL of the FastAPI service.
        timeout (int, default=30): HTTP request timeout in seconds.

    Returns:
        Dict[str, Any]: Taxonomy artifact with a `columns` key, or `{"columns": {}}`
            on malformed responses.

    Raises:
        requests.HTTPError: On non-2xx responses.
    """
    response = requests.get(
        f"{fastapi_url}/v1/vocab/german",
        headers=_api_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        return {"columns": {}}
    if "columns" not in data or not isinstance(data["columns"], dict):
        data["columns"] = {}
    return data


# The German result card, in display order: (result key, label, is_list).
#
# Every field is always rendered — a programme that does not state one shows "N/A"
# rather than dropping the line, so the card has the same shape for every result and
# a reader can tell "not stated" from "you scrolled past it".
GERMAN_RESULT_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("project_short_description", "Short description", False),
    ("project_full_description", "Full description", False),
    ("funding_location", "Target area", True),
    ("funding_type", "Type of funding", True),
    ("eligible_applicants", "Eligible applicants", True),
    ("funding_area", "Funding area", True),
    ("status_note", "Status", False),
    ("deadlines", "Deadlines", False),
    ("keywords_extracted", "Keywords", True),
    ("contact_info_institution", "Contact", False),
)

# Only the short description stays visible; everything after it is folded into an
# expander so a page of results can be scanned by title and summary alone. The split
# is presentation only — together the two halves are still GERMAN_RESULT_FIELDS.
GERMAN_SUMMARY_FIELDS = GERMAN_RESULT_FIELDS[:1]
GERMAN_DETAIL_FIELDS = GERMAN_RESULT_FIELDS[1:]

DETAILS_EXPANDER_LABEL = "More details"

PLACEHOLDER_VALUE = "N/A"

# How much of the EU card's headline text stays outside the expander. The topic
# destination runs to several thousand characters — it describes a whole work
# programme destination, not one topic — and printing it in full would make a
# single result taller than a screen.
EU_CARD_DESCRIPTION_CHARS = 400


def display_value(value: Any) -> str:
    """Render a scalar result field, falling back to ``"N/A"``.

    Covers the three ways a field can be absent by the time it reaches the page: the
    data pipeline filled it with the ``"N/A"`` placeholder, the API defaulted it to
    an empty string because the collection has no such field, or the key is missing
    from the result dict entirely.

    Args:
        value (Any): Raw field value from a result dict.

    Returns:
        str: The stripped value, or ``"N/A"``.
    """
    if value is None:
        return PLACEHOLDER_VALUE
    text = str(value).strip()
    return text or PLACEHOLDER_VALUE


def render_relevance(result: Dict, rank: int | None = None) -> None:
    """Render a result's relevance line.

    The backend's ``relative_score`` is normalised against the best match *in this
    response*, so the top card is always 100% — for a nonsense query as much as for a
    real one. Labelling that bare number "Score" claimed an absolute quality it does
    not have, so the line now names the scale it is on and leads with the rank, which
    is the part that actually means something. ``SearchResponse.weak_match`` carries
    the absolute signal and is rendered once above the whole list, not per card.

    Declared once and shared by both cards so the two cannot drift into describing
    the same number differently.

    Args:
        result (Dict): Project dict as returned by `search_projects`.
        rank (int | None, default=None): 1-based position in the result list. When
            omitted the rank prefix is left off.
    """
    share = result.get("relative_score", 0) * 100
    position = f"#{rank} — " if rank is not None else ""
    st.write(f"**Relevance:** {position}{share:.0f}% of the best match for this query")


def render_german_project_result(result: Dict, rank: int | None = None) -> None:
    """Render a German federal funding project as a Streamlit card.

    Displays the title as a link to the programme page and the `GERMAN_SUMMARY_FIELDS`
    rows, then folds the `GERMAN_DETAIL_FIELDS` rows into a collapsed expander, then
    the relevance line. List fields are joined via `safe_join`; both helpers fall back
    to "N/A", so the card never omits a line.

    Args:
        result (Dict): Project dict as returned by `search_projects`.
        rank (int | None, default=None): 1-based position in the result list, shown
            in the relevance line. See `render_relevance`.
    """
    st.subheader(
        f"[{result.get('project_title', 'No title')}]"
        f"({result.get('project_website', '#')})"
    )

    _render_german_fields(result, GERMAN_SUMMARY_FIELDS)
    with st.expander(DETAILS_EXPANDER_LABEL):
        _render_german_fields(result, GERMAN_DETAIL_FIELDS)

    render_relevance(result, rank)


def _render_german_fields(
        result: Dict,
        fields: tuple[tuple[str, str, bool], ...]
) -> None:
    """Render a run of German card rows as ``**Label:** value`` markdown lines.

    Args:
        result (Dict): Project dict as returned by `search_projects`.
        fields (tuple[tuple[str, str, bool], ...]): Rows to render, in the
            `GERMAN_RESULT_FIELDS` ``(key, label, is_list)`` shape.
    """
    for field, label, is_list in fields:
        value = result.get(field)
        rendered = safe_join(value) if is_list else display_value(value)
        st.markdown(f"**{label}:** {rendered}")


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a datetime-like value into a ``datetime`` object, returning ``None`` on failure.

    Args:
        value (Any): ISO-8601 string, ``datetime`` instance, or ``None``.

    Returns:
        datetime | None: Parsed ``datetime``, or ``None`` when unparseable.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _truncate(text: str, limit: int = EU_CARD_DESCRIPTION_CHARS) -> str:
    """Shorten `text` to `limit` characters, appending an ellipsis when cut.

    Args:
        text (str): Text to shorten.
        limit (int): Maximum characters to keep before the ellipsis.

    Returns:
        str: `text` unchanged when it fits, otherwise its truncated prefix + "…".
    """
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def render_eu_project_result(result: Dict, rank: int | None = None) -> None:
    """Render an EU funding call as a Streamlit card.

    Displays the title (linked to the EU portal) above a truncated headline, folds
    the full topic description and the two dates into a collapsed expander, then
    shows the relevance line. Both dates are always rendered, falling back to "N/A"
    — the same rule as the German card, so a reader can tell "not stated" from "you
    scrolled past it".

    The headline is the topic's *destination* — the aims of the work programme
    destination it sits under — which says what the call is ultimately for far more
    briefly than the topic text does. The portal states it on Horizon topics only,
    roughly one open call in eight, so the card falls back to the topic description
    rather than leading most results with "N/A". Either way the topic description is
    in the expander, so nothing the card drops is lost.

    Args:
        result (Dict): Project dict as returned by `search_projects`.
        rank (int | None, default=None): 1-based position in the result list, shown
            in the relevance line. See `render_relevance`.
    """
    st.subheader(
        f"[{result.get('project_title', 'No title')}]"
        f"({result.get('project_website', '#')})"
    )

    destination = display_value(result.get("topic_destination"))
    description = display_value(result.get("project_full_description"))
    headline = description if destination == PLACEHOLDER_VALUE else destination
    st.write("**Description:**", _truncate(headline))

    with st.expander(DETAILS_EXPANDER_LABEL):
        st.write("**Topic description:**", description)
        st.write("**Planned opening date:**", _display_date(result.get("date_1")))
        st.write("**Deadline:**", _display_date(result.get("date_2")))

    render_relevance(result, rank)


#: One display format for every date the UI shows, so a result card, the watchlist
#: and the saved-search pages cannot drift apart. Day-month-year with a 24-hour
#: clock and an abbreviated month reads unambiguously to both German and English
#: users, which a numeric-only format does not.
DATE_DISPLAY_FORMAT = "%d %b %Y, %H:%M"


def format_timestamp(value: datetime) -> str:
    """Format a known-present datetime for display.

    For the pages that hold a real ``datetime`` from the database and have nothing
    to fall back to. Use `_display_date` where the value may be absent or a string.

    Args:
        value (datetime): The timestamp to render.

    Returns:
        str: Formatted per `DATE_DISPLAY_FORMAT`.
    """
    return value.strftime(DATE_DISPLAY_FORMAT)


def _display_date(value: Any) -> str:
    """Format a datetime-like value for the EU card, falling back to ``"N/A"``.

    Args:
        value (Any): ISO-8601 string, ``datetime`` instance, or ``None``.

    Returns:
        str: Date formatted per `DATE_DISPLAY_FORMAT`, or ``"N/A"`` when unparseable.
    """
    parsed = _parse_datetime(value)
    if parsed is None:
        return PLACEHOLDER_VALUE
    return format_timestamp(parsed)


def friendly_search_error(error: Exception) -> str:
    """Map a search exception to a user-friendly error message for display in the UI.

    Args:
        error (Exception): Exception raised during `search_projects`.

    Returns:
        str: Human-readable message suitable for `st.error(...)`.
    """
    if isinstance(error, (requests.exceptions.ConnectionError, ConnectionRefusedError)):
        return (
            "Search service is still starting up."
            " Data download or embedding may still be in progress. "
            "Please wait a moment and try again."
        )
    if isinstance(error, requests.exceptions.Timeout):
        return (
            "The search request is taking longer than expected."
            " Please try again in a moment."
        )
    if isinstance(error, requests.exceptions.HTTPError):
        if error.response is not None and error.response.status_code == 503:
            return (
                "The embedding service is warming up."
                " Please retry in a few seconds."
            )
        return "Search service returned an unexpected response. Please try again."
    return "Something went wrong while searching. Please try again."
