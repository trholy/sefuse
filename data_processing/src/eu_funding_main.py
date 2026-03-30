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
    UniqueValueExtractor,
)
from data_processing.utils import EuFundingFetcher

logger = logging.getLogger(__name__)


def _load_or_fetch_open_calls(
    config: EuFundingConfig,
    fetcher: EuFundingFetcher,
) -> list[dict]:
    try:
        calls = fetcher.fetch_open_and_forthcoming_calls(
            page_size=config.page_size,
            max_pages=config.max_pages,
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
    config = EuFundingConfig()

    fetcher = EuFundingFetcher(
        api_url=config.api_url,
        api_key=config.api_key,
        timeout_seconds=config.request_timeout_seconds,
        page_delay_seconds=config.page_delay_seconds,
    )

    eu_calls = _load_or_fetch_open_calls(config, fetcher)

    eu_processor = EuFundingProcessor(html_cleaner=HtmlCleaner())
    eu_df = eu_processor.transform(eu_calls)

    common_pipeline = CommonDataPipeline(
        cleaner=DataCleaner(HtmlCleaner()),
        value_extractor=UniqueValueExtractor(),
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
        export_file_prefix="eu_",
        columns_to_drop_before_store=[UUID_SOURCE_COLUMN],
        taxonomy_path=config.taxonomy_json,
        taxonomy_domain="eu",
    )

if __name__ == "__main__":
    run_eu_funding_pipeline()
