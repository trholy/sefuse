import os
from dataclasses import dataclass
from pathlib import Path


GERMAN_FUNDING_DATA_URL = os.getenv(
    "GERMAN_FUNDING_DATA_URL",
    "https://foerderdatenbankdump.fra1.cdn.digitaloceanspaces.com/data/parquet_data.zip",
)
EU_API_URL = os.getenv(
    "EU_API_URL",
    "https://api.tech.ec.europa.eu/search-api/prod/rest/search",
)
EU_API_KEY = os.getenv("EU_API_KEY", "SEDIA")
EU_PAGE_SIZE = int(os.getenv("EU_PAGE_SIZE", "50"))
EU_MAX_PAGES = int(os.getenv("EU_MAX_PAGES", "100"))
EU_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("EU_REQUEST_TIMEOUT_SECONDS", "30")
)
EU_PAGE_DELAY_SECONDS = float(os.getenv("EU_PAGE_DELAY_SECONDS", "0.2"))

@dataclass(frozen=True)
class GermanFundingConfig:
    data_dir: Path = Path("data")
    zip_url: str = GERMAN_FUNDING_DATA_URL

    zip_path: Path = data_dir / "german_parquet_data.zip"
    raw_parquet: Path = data_dir / "german_parquet_data.parquet"
    cleaned_parquet: Path = data_dir / "german_parquet_data_cleaned.parquet"
    uuid_parquet: Path = data_dir / "german_parquet_data_uuid.parquet"


@dataclass(frozen=True)
class EuFundingConfig:
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
