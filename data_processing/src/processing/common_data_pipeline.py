from pathlib import Path

import polars as pl

from .cleaner import DataCleaner
from .uuid_generator import UuidGenerator
from .value_extractor import UniqueValueExtractor


DEFAULT_EXPORT_COLUMNS = [
    "funding_type",
    "funding_area",
    "funding_location",
    "eligible_applicants",
]


class CommonDataPipeline:
    def __init__(
        self,
        cleaner: DataCleaner,
        value_extractor: UniqueValueExtractor,
        uuid_generator: UuidGenerator,
    ):
        self._cleaner = cleaner
        self._value_extractor = value_extractor
        self._uuid_generator = uuid_generator

    def process_and_store(
        self,
        df: pl.DataFrame,
        cleaned_path: Path,
        uuid_path: Path,
        source_column: str,
        data_dir: Path,
        export_columns: list[str] | None = None,
        export_file_prefix: str = "",
        columns_to_drop_before_store: list[str] | None = None,
    ) -> None:
        cleaned_df = self._cleaner.clean_dataframe(df)

        df_with_uuid = self._uuid_generator.add_uuid_column(
            cleaned_df,
            source_column=source_column,
        )

        columns_to_drop = columns_to_drop_before_store or []
        cleaned_output_df = cleaned_df.drop(columns_to_drop, strict=False)
        uuid_output_df = df_with_uuid.drop(columns_to_drop, strict=False)

        cleaned_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_output_df.write_parquet(cleaned_path)

        columns_to_export = export_columns or DEFAULT_EXPORT_COLUMNS
        data_dir.mkdir(parents=True, exist_ok=True)
        for column in columns_to_export:
            values = self._value_extractor.extract(cleaned_output_df, column)
            self._value_extractor.save(
                values,
                data_dir / f"{export_file_prefix}{column}.txt",
            )

        uuid_path.parent.mkdir(parents=True, exist_ok=True)
        uuid_output_df.write_parquet(uuid_path)
