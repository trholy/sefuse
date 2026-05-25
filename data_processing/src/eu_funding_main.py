import logging
import uuid

import requests

from data_processing.config import EuFundingConfig
from data_processing.processing import (
    CommonDataPipeline,
    DataCleaner,
    EuFundingProcessor,
    HtmlCleaner,
    UUID_SOURCE_COLUMN,
    UuidGenerator,
)
from data_processing.utils import EuFundingFetcher

logger = logging.getLogger(__name__)


def _load_or_fetch_open_calls(
    config: EuFundingConfig,
    fetcher: EuFundingFetcher,
    max_pages: int | None = None,
) -> list[dict]:
    """Fetch EU calls from the API, falling back to the cached JSON on network errors.

    Saves freshly fetched calls to `config.raw_json` before returning them.
    If the API request fails and no cache file exists, the exception is re-raised.

    Args:
        config (EuFundingConfig): Pipeline configuration with API settings and file paths.
        fetcher (EuFundingFetcher): Configured fetcher instance.
        max_pages (int | None, default=None): Maximum pages to fetch; ``None`` means no limit.

    Returns:
        list[dict]: Open/forthcoming EU call records (live or cached).

    Raises:
        requests.RequestException: If the API is unreachable and no cache exists.
    """
    try:
        calls = fetcher.fetch_open_and_forthcoming_calls(
            page_size=config.page_size,
            max_pages=max_pages,
        )
        fetcher.save(calls, config.raw_json)
        return calls
    except requests.RequestException as error:
        if config.raw_json.exists():
            logger.warning(
                "EU API request failed (%s). Falling back to cached file: %s",
                error,
                config.raw_json,
            )
            return fetcher.load(config.raw_json)
        raise


def run_eu_funding_pipeline() -> None:
    """Fetch, process, and store the EU funding dataset end-to-end.

    Orchestrates the full EU pipeline:
    1. Fetches open/forthcoming calls via `EuFundingFetcher` (falls back to cache).
    2. Transforms raw dicts to a typed DataFrame via `EuFundingProcessor`.
    3. Runs `CommonDataPipeline.process_and_store` to clean, canonicalise the
       `funding_area` taxonomy, assign UUIDs, and write the Parquet files plus
       the taxonomy JSON to `EuFundingConfig.data_dir`.

    Invoked by the FastAPI APScheduler cron job and on startup.
    """
    config = EuFundingConfig()

    fetcher = EuFundingFetcher(
        api_url=config.api_url,
        api_key=config.api_key,
        timeout_seconds=config.request_timeout_seconds,
        page_delay_seconds=config.page_delay_seconds,
    )

    eu_calls = _load_or_fetch_open_calls(config, fetcher, max_pages=config.max_pages)

    eu_processor = EuFundingProcessor(html_cleaner=HtmlCleaner())
    eu_df = eu_processor.transform(eu_calls)

    common_pipeline = CommonDataPipeline(
        cleaner=DataCleaner(HtmlCleaner()),
        uuid_generator=UuidGenerator(
            namespace=uuid.UUID("12345678-1234-5678-1234-567812345678")
        ),
    )

    common_pipeline.process_and_store(
        df=eu_df,
        cleaned_path=config.cleaned_parquet,
        uuid_path=config.uuid_parquet,
        source_column=UUID_SOURCE_COLUMN,
        data_dir=config.data_dir,
        export_columns=["funding_area"],
        columns_to_drop_before_store=[UUID_SOURCE_COLUMN],
        taxonomy_path=config.taxonomy_json,
        taxonomy_domain="eu",
    )

if __name__ == "__main__":
    run_eu_funding_pipeline()
