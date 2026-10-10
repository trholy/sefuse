"""Entry point for the EU funding data pipeline (fetch → process → store)."""

import logging

import requests

from data_processing.config import EuFundingConfig, EU_UUID_NAMESPACE
from data_processing.processing import (
    CommonDataPipeline,
    DataCleaner,
    EuFundingProcessor,
    HtmlCleaner,
    MAX_DROP_RATIO,
    UUID_SOURCE_COLUMN,
    UuidGenerator,
    drop_ratio,
)
from data_processing.utils import EuFundingFetcher, TruncatedFetchError

logger = logging.getLogger(__name__)


def _cache_is_safe_to_overwrite(
    calls: list[dict],
    config: EuFundingConfig,
    fetcher: EuFundingFetcher,
) -> bool:
    """Return whether `calls` is complete enough to replace the cached snapshot.

    The cache is the fallback used whenever the API is unreachable, so overwriting it
    with a short fetch would destroy the only good copy and make the truncation
    permanent.

    Args:
        calls (list[dict]): Freshly fetched call records.
        config (EuFundingConfig): Pipeline configuration, for the cache path.
        fetcher (EuFundingFetcher): Used to read the cached snapshot back.

    Returns:
        bool: True when there is no usable cache to compare against, or when the
            record count did not fall by more than ``DATA_REFRESH_MAX_DROP_RATIO``.
    """
    if not config.raw_json.exists():
        return True
    try:
        cached_count = len(fetcher.load(config.raw_json))
    except Exception as error:
        logger.warning("Could not read cached EU calls (%s) — overwriting", error)
        return True
    if cached_count == 0:
        return True

    ratio = drop_ratio(cached_count, len(calls))
    if ratio > MAX_DROP_RATIO:
        logger.error(
            "EU fetch returned %s calls, down from %s cached (%.1f%% drop, limit "
            "%.1f%%). Keeping the cached snapshot.",
            len(calls), cached_count, ratio * 100, MAX_DROP_RATIO * 100,
        )
        return False
    return True


def _load_or_fetch_open_calls(
    config: EuFundingConfig,
    fetcher: EuFundingFetcher,
    max_pages: int | None = None,
) -> list[dict]:
    """Fetch EU calls from the API, falling back to the cached JSON on network errors.

    Saves freshly fetched calls to `config.raw_json` before returning them, but only
    when the fetch looks complete — see `_cache_is_safe_to_overwrite`. A fetch that
    stopped early falls back to the cache rather than propagating a short result set
    into the Parquet file, where the missing projects would read as withdrawn.

    Args:
        config (EuFundingConfig): Pipeline configuration with API settings and file paths.
        fetcher (EuFundingFetcher): Configured fetcher instance.
        max_pages (int | None, default=None): Maximum pages to fetch; ``None`` means no limit.

    Returns:
        list[dict]: Open/forthcoming EU call records (live or cached).

    Raises:
        requests.RequestException: If the API is unreachable and no cache exists.
        TruncatedFetchError: If pagination stopped early and no cache exists.
    """
    try:
        calls = fetcher.fetch_open_and_forthcoming_calls(
            page_size=config.page_size,
            max_pages=max_pages,
        )
        if not _cache_is_safe_to_overwrite(calls, config, fetcher):
            return fetcher.load(config.raw_json)
        fetcher.save(calls, config.raw_json)
        return calls
    except (requests.RequestException, TruncatedFetchError) as error:
        if config.raw_json.exists():
            logger.warning(
                "EU fetch failed (%s). Falling back to cached file: %s",
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
            namespace=EU_UUID_NAMESPACE
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
