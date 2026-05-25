import uuid
import logging

import polars as pl

from data_processing.config import GermanFundingConfig
from data_processing.processing import (
    CommonDataPipeline,
    DataCleaner,
    GermanFundingProcessor,
    HtmlCleaner,
    UuidGenerator,
)
from data_processing.utils import FileDownloader, ZipExtractor

logger = logging.getLogger(__name__)


def run_german_funding_pipeline() -> None:
    """Download, extract, clean, and embed the German federal funding dataset.

    Orchestrates the full pipeline:
    1. Downloads the ZIP from `GermanFundingConfig.zip_url`.
    2. Extracts `data.parquet` from the archive.
    3. Renames date columns via `GermanFundingProcessor`.
    4. Runs `CommonDataPipeline.process_and_store` to clean, canonicalise taxonomy,
       assign UUIDs, and write both the cleaned and UUID Parquet files plus the
       taxonomy JSON to `GermanFundingConfig.data_dir`.

    Invoked by the FastAPI APScheduler cron job and on startup.
    """
    logger.info("German pipeline: starting dataset download and processing")
    config = GermanFundingConfig()

    downloader = FileDownloader()
    extractor = ZipExtractor()

    logger.info("German pipeline: downloading dataset from %s", config.zip_url)
    downloader.download(config.zip_url, config.zip_path)
    logger.info("German pipeline: extracting parquet from %s", config.zip_path)
    extractor.extract_file(
        zip_path=config.zip_path,
        filename="data.parquet",
        target_path=config.raw_parquet,
    )

    logger.info("German pipeline: loading parquet %s", config.raw_parquet)
    raw_df = pl.read_parquet(config.raw_parquet)
    logger.info("German pipeline: loaded %s rows", raw_df.height)
    german_df = GermanFundingProcessor.transform(raw_df)

    common_pipeline = CommonDataPipeline(
        cleaner=DataCleaner(HtmlCleaner()),
        uuid_generator=UuidGenerator(
            namespace=uuid.UUID("12345678-1234-5678-1234-567812345678")
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
