import time
from typing import List, Any, Union, Dict
import logging
from datetime import datetime

import requests
import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_join(
        value: Union[List[Any], None],
        sep: str = ", ",
        default: str = "N/A"
) -> str:
    """Safely join lists or return default for empty values."""
    if not value:
        return default
    if isinstance(value, (list, tuple, set)):
        return sep.join(str(v) for v in value if v is not None)
    return str(value)


def normalize_list(value: Any) -> List[str]:
    """Ensure the value is always a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def read_extracted_filter_options(
        file_path: str,
        retries: int = 10,
        delay: float = 1
) -> List[str]:
    """Read lines from a file with retry logic."""
    attempt = 0
    while True:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError as e:
            attempt += 1
            logger.warning(f"File not found (attempt {attempt}): {file_path}")
            if attempt >= retries:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 30)

def apply_filters(
        matches: List[Dict],
        filters: Dict[str, List[str]]
) -> List[Dict]:
    """Filter the API results according to sidebar selections."""
    filtered = []
    for r in matches:
        funding_location = normalize_list(r.get("funding_location"))
        funding_type = normalize_list(r.get("funding_type"))
        eligible_applicants = normalize_list(r.get("eligible_applicants"))
        funding_area = normalize_list(r.get("funding_area"))
        short_description = r.get("project_short_description")
        full_description = r.get("project_full_description")

        if filters["locations"] and not any(
                loc in funding_location for loc in filters["locations"]):
            continue
        if filters["funding_type"] and not any(
                ft in funding_type for ft in filters["funding_type"]):
            continue
        if filters["eligible"] and not any(
                el in eligible_applicants for el in filters["eligible"]):
            continue
        if filters["funding_area"] and not any(
                area in funding_area for area in filters["funding_area"]):
            continue
        if filters["drop_na"] and "N/A" == short_description == full_description:
            continue
        filtered.append(r)
    return filtered


def aggregate_chunks(matches: List[Dict]) -> List[Dict]:
    """
    Aggregate multiple chunk results per project into a single entry.
    Keeps metadata from the first occurrence and uses the max score among chunks.
    """
    aggregated: Dict[str, Dict] = {}
    for r in matches:
        project_id = r.get("project_id")
        if not project_id:
            continue
        if project_id not in aggregated:
            aggregated[project_id] = r.copy()
        else:
            # Update score if this chunk has higher similarity
            aggregated[project_id]["matching_score"] = max(
                aggregated[project_id].get("matching_score", 0),
                r.get("matching_score", 0)
            )
    return list(aggregated.values())


def search_projects(
        fastapi_url: str,
        model: str,
        query: str,
        search_limit: int,
        semantic_weight: float,
        endpoint: str,
        timeout: int = 30
) -> List[Dict]:
    """Run semantic search request against the backend and return matches."""
    response = requests.post(
        f"{fastapi_url}{endpoint}",
        json={
            "model": model,
            "messages": [{"role": "user", "content": query}],
            "limit": search_limit,
            "semantic_weight": semantic_weight,
        },
        timeout=timeout
    )
    response.raise_for_status()
    data = response.json()
    return data.get("matches", [])


def render_german_project_result(result: Dict) -> None:
    """Render a single funding project card."""
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
    """Render a single EU funding project card."""
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
