"""Entry point for the German federal funding data pipeline (download → parse → process → store)."""

import logging

from data_processing.config import GermanFundingConfig, GERMAN_UUID_NAMESPACE
from data_processing.processing import (
    CommonDataPipeline,
    DataCleaner,
    GermanFundingProcessor,
    HtmlCleaner,
    UuidGenerator,
)
from data_processing.utils import FileDownloader, GermanFundingCsvParser

logger = logging.getLogger(__name__)


def run_german_funding_pipeline() -> None:
    """Download, parse, clean, and store the German federal funding dataset.

    Orchestrates the full pipeline:
    1. Downloads the published CSV from `GermanFundingConfig.csv_url`.
    2. Parses the CSV into a DataFrame via `GermanFundingCsvParser`.
    3. Renames date/absence columns via `GermanFundingProcessor`.
    4. Runs `CommonDataPipeline.process_and_store` to clean, canonicalise taxonomy,
       assign UUIDs, and write both the cleaned and UUID Parquet files plus the
       taxonomy JSON to `GermanFundingConfig.data_dir`.

    Invoked by the FastAPI APScheduler cron job and on startup.
    """
    logger.info("German pipeline: starting dataset download and processing")
    config = GermanFundingConfig()

    downloader = FileDownloader()

    logger.info("German pipeline: downloading CSV from %s", config.csv_url)
    try:
        downloader.download(config.csv_url, config.csv_path)
    except Exception as exc:
        if config.csv_path.exists():
            logger.warning(
                "German pipeline: download failed (%s) — continuing with existing file %s",
                exc,
                config.csv_path,
            )
        else:
            raise RuntimeError(
                f"German pipeline: download failed and no local CSV found at {config.csv_path}. "
                "Place the CSV export manually at that path to proceed."
            ) from exc

    logger.info("German pipeline: parsing CSV from %s", config.csv_path)
    raw_df = GermanFundingCsvParser().parse(config.csv_path)
    logger.info("German pipeline: loaded %s rows", raw_df.height)
    german_df = GermanFundingProcessor.transform(raw_df)

    common_pipeline = CommonDataPipeline(
        cleaner=DataCleaner(HtmlCleaner()),
        uuid_generator=UuidGenerator(
            namespace=GERMAN_UUID_NAMESPACE
        ),
    )

    common_pipeline.process_and_store(
        df=german_df,
        cleaned_path=config.cleaned_parquet,
        uuid_path=config.uuid_parquet,
        source_column="id_hash",
        data_dir=config.data_dir,
        taxonomy_path=config.taxonomy_json,
        taxonomy_domain="german",
    )
    logger.info("German pipeline: completed")

if __name__ == "__main__":
    run_german_funding_pipeline()
