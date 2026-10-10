"""Configuration module for the SeFuSe data-processing pipelines.

Reads environment variables for API endpoints, credentials, and pagination
settings. Exposes two frozen dataclasses — `GermanFundingConfig` and
`EuFundingConfig` — that bundle all file paths and runtime parameters for
their respective funding pipelines.
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

GERMAN_UUID_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")
EU_UUID_NAMESPACE = uuid.UUID("87654321-4321-8765-4321-876543218765")


# CorrelAid's published Förderdatenbank dataset (CC BY-ND 4.0, BMWE as rights holder).
# A contract-checked CSV rebuilt weekly from the BMWE XML export, with nested values
# JSON-encoded per cell. See data_processing/CLAUDE.md for the column contract.
GERMAN_FUNDING_DATA_URL = os.getenv(
    "GERMAN_FUNDING_DATA_URL",
    "https://fdb.cdl.correlaid.org/data/programme.csv",
)
EU_API_URL = os.getenv(
    "EU_API_URL",
    "https://api.tech.ec.europa.eu/search-api/prod/rest/search",
)
EU_API_KEY = os.getenv("EU_API_KEY", "")
EU_PAGE_SIZE = int(os.getenv("EU_PAGE_SIZE", "50"))
EU_MAX_PAGES = int(os.getenv("EU_MAX_PAGES", "100"))
EU_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("EU_REQUEST_TIMEOUT_SECONDS", "30")
)
EU_PAGE_DELAY_SECONDS = float(os.getenv("EU_PAGE_DELAY_SECONDS", "0.2"))

@dataclass(frozen=True)
class GermanFundingConfig:
    """File paths and download URL for the German federal funding pipeline.

    All paths default to a `data/` subdirectory relative to the working directory.
    Override `GERMAN_FUNDING_DATA_URL` via environment variable to change the source.
    """

    data_dir: Path = Path("data")
    csv_url: str = GERMAN_FUNDING_DATA_URL

    csv_path: Path = data_dir / "german_programme.csv"
    cleaned_parquet: Path = data_dir / "german_parquet_data_cleaned.parquet"
    uuid_parquet: Path = data_dir / "german_parquet_data_uuid.parquet"
    taxonomy_json: Path = data_dir / "taxonomy_german.json"


@dataclass(frozen=True)
class EuFundingConfig:
    """API settings and file paths for the EU funding pipeline.

    API parameters (URL, key, page size, timeouts) are read from environment variables
    and default to the public endpoint. All file paths live under `data/`.
    """

    data_dir: Path = Path("data")

    api_url: str = EU_API_URL
    api_key: str = EU_API_KEY
    page_size: int = EU_PAGE_SIZE
    max_pages: int = EU_MAX_PAGES
    request_timeout_seconds: float = EU_REQUEST_TIMEOUT_SECONDS
    page_delay_seconds: float = EU_PAGE_DELAY_SECONDS

    raw_json: Path = data_dir / "eu_open_calls.json"
    cleaned_parquet: Path = data_dir / "eu_parquet_data_cleaned.parquet"
    uuid_parquet: Path = data_dir / "eu_parquet_data_uuid.parquet"
    taxonomy_json: Path = data_dir / "taxonomy_eu.json"
