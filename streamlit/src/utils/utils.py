import time
from typing import List, Any, Union, Dict
import logging

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
