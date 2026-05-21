import os
from typing import List, Any, Union, Dict
import logging
from datetime import datetime

import requests
import streamlit as st

logging.basicConfig(level=logging.INFO)
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
) -> List[Dict]:
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
        List[Dict]: List of matching project dicts from the `matches` key.

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
    return data.get("matches", [])


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


def render_german_project_result(result: Dict) -> None:
    """Render a German federal funding project as a Streamlit card.

    Displays title (linked to project website), short/full descriptions, on-website
    and last-updated dates, funding type, location, area, eligible applicants, and score.

    Args:
        result (Dict): Project dict as returned by `search_projects`.
    """
    st.subheader(
        f"[{result.get('project_title', 'No title')}]"
        f"({result.get('project_website', '#')})"
    )
    st.write(
        "**Short description:**",
        result.get("project_short_description", "N/A")
    )
    st.write(
        "**Full description:**",
        result.get("project_full_description", "N/A")
    )

    try:
        on_website_from = datetime.fromisoformat(result.get("date_1"))
        last_updated = datetime.fromisoformat(result.get("date_2"))
        st.write(
            "**On the website since:**",
            on_website_from.strftime("%d %b %Y, %H:%M")
        )
        st.write(
            "**Last updated:**",
            last_updated.strftime("%d %b %Y, %H:%M")
        )
    except Exception:
        pass

    st.markdown(f"**Type of funding:** {safe_join(result.get('funding_type'))}")
    st.markdown(f"**Target area:** {safe_join(result.get('funding_location'))}")
    st.markdown(f"**Funding area:** {safe_join(result.get('funding_area'))}")
    st.markdown(f"**Eligible applicants:** {safe_join(result.get('eligible_applicants'))}")
    st.write(f"**Score:** {result.get('matching_score', 0) * 100:.1f} %")


def _parse_datetime(value: Any) -> datetime | None:
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


def render_eu_project_result(result: Dict) -> None:
    """Render an EU funding call as a Streamlit card.

    Displays title (linked to the EU portal), full description, planned opening
    date, deadline, and matching score.

    Args:
        result (Dict): Project dict as returned by `search_projects`.
    """
    st.subheader(
        f"[{result.get('project_title', 'No title')}]"
        f"({result.get('project_website', '#')})"
    )
    st.write("**Description:**", result.get("project_full_description", "N/A"))

    start_date = _parse_datetime(result.get("date_1"))
    deadline = _parse_datetime(result.get("date_2"))

    if start_date is not None:
        st.write(
            "**Planned opening date:**",
            start_date.strftime("%d %b %Y, %H:%M")
        )
    if deadline is not None:
        st.write(
            "**Deadline:**",
            deadline.strftime("%d %b %Y, %H:%M")
        )

    st.write(f"**Score:** {result.get('matching_score', 0) * 100:.1f} %")


def _friendly_search_error(error: Exception) -> str:
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
        return "Search service returned an unexpected response. Please try again."
    return "Something went wrong while searching. Please try again."
