import uuid
import polars as pl

from data_processing.config import DataConfig
from data_processing.utils import FileDownloader
from data_processing.utils import ZipExtractor
from data_processing.processing import DataCleaner, HtmlCleaner
from data_processing.processing import UuidGenerator
from data_processing.processing import UniqueValueExtractor


def data_processing_pipeline() -> None:
    config = DataConfig()

    downloader = FileDownloader()
    extractor = ZipExtractor()

    downloader.download(config.zip_url, config.zip_path)
    extractor.extract_file(
        zip_path=config.zip_path,
        filename="data.parquet",
        target_path=config.raw_parquet
    )

    df = pl.read_parquet(config.raw_parquet)

    cleaner = DataCleaner(HtmlCleaner())
    cleaned_df = cleaner.clean_dataframe(df)
    cleaned_df.write_parquet(config.cleaned_parquet)

    value_extractor = UniqueValueExtractor()

    export_columns = [
        "funding_type",
        "funding_area",
        "funding_location",
        "eligible_applicants"
    ]

    for column in export_columns:
        values = value_extractor.extract(cleaned_df, column)
        value_extractor.save(
            values,
            config.data_dir / f"{column}.txt"
        )

    uuid_generator = UuidGenerator(
        namespace=uuid.UUID("12345678-1234-5678-1234-567812345678")
    )

    df_with_uuid = uuid_generator.add_uuid_column(
        cleaned_df,
        source_column="id_hash"
    )

    df_with_uuid.write_parquet(config.uuid_parquet)


if __name__ == "__main__":
    data_processing_pipeline()
