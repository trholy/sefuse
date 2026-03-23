import uuid

import polars as pl

from data_processing.config import GermanFundingConfig
from data_processing.processing import (
    CommonDataPipeline,
    DataCleaner,
    GermanFundingProcessor,
    HtmlCleaner,
    UuidGenerator,
    UniqueValueExtractor,
)
from data_processing.utils import FileDownloader, ZipExtractor


def run_german_funding_pipeline() -> None:
    config = GermanFundingConfig()

    downloader = FileDownloader()
    extractor = ZipExtractor()

    downloader.download(config.zip_url, config.zip_path)
    extractor.extract_file(
        zip_path=config.zip_path,
        filename="data.parquet",
        target_path=config.raw_parquet,
    )

    raw_df = pl.read_parquet(config.raw_parquet)
    german_df = GermanFundingProcessor.transform(raw_df)

    common_pipeline = CommonDataPipeline(
        cleaner=DataCleaner(HtmlCleaner()),
        value_extractor=UniqueValueExtractor(),
        uuid_generator=UuidGenerator(
            namespace=uuid.UUID("12345678-1234-5678-1234-567812345678")
        ),
    )

    common_pipeline.process_and_store(
        df=german_df,
        cleaned_path=config.cleaned_parquet,
        uuid_path=config.uuid_parquet,
        source_column="id_hash",
        export_file_prefix="german_",
        data_dir=config.data_dir,
    )

if __name__ == "__main__":
    run_german_funding_pipeline()
