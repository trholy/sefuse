from pathlib import Path

import polars as pl

from .cleaner import DataCleaner
from .taxonomy_contract_builder import TaxonomyContractBuilder
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
        taxonomy_builder: TaxonomyContractBuilder | None = None,
    ):
        self._cleaner = cleaner
        self._value_extractor = value_extractor
        self._uuid_generator = uuid_generator
        self._taxonomy_builder = taxonomy_builder or TaxonomyContractBuilder()

    def process_and_store(
        self,
        df: pl.DataFrame,
        cleaned_path: Path,
        uuid_path: Path,
        source_column: str,
        data_dir: Path,
        taxonomy_path: Path,
        export_columns: list[str] | None = None,
        export_file_prefix: str = "",
        columns_to_drop_before_store: list[str] | None = None,
        taxonomy_domain: str = "german",
    ) -> None:
        columns_to_export = export_columns or DEFAULT_EXPORT_COLUMNS

        cleaned_df = self._cleaner.clean_dataframe(df)
        cleaned_df, taxonomy_columns = self._taxonomy_builder.canonicalize_dataframe(
            cleaned_df,
            columns_to_export,
        )
        taxonomy_artifact = self._taxonomy_builder.build_taxonomy_artifact(
            domain=taxonomy_domain,
            columns=taxonomy_columns,
        )

        df_with_uuid = self._uuid_generator.add_uuid_column(
            cleaned_df,
            source_column=source_column,
        )

        columns_to_drop = columns_to_drop_before_store or []
        cleaned_output_df = cleaned_df.drop(columns_to_drop, strict=False)
        uuid_output_df = df_with_uuid.drop(columns_to_drop, strict=False)

        cleaned_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_output_df.write_parquet(cleaned_path)

        data_dir.mkdir(parents=True, exist_ok=True)
        for column in columns_to_export:
            values: list[str] = []
            artifact_columns = taxonomy_artifact.get("columns")
            entries = artifact_columns.get(column, []) if isinstance(artifact_columns, dict) else []
            for entry in entries:
                if isinstance(entry, dict):
                    canonical = entry.get("canonical")
                    if isinstance(canonical, str) and canonical:
                        values.append(canonical)
            self._value_extractor.save(
                values,
                data_dir / f"{export_file_prefix}{column}.txt",
            )

        uuid_path.parent.mkdir(parents=True, exist_ok=True)
        uuid_output_df.write_parquet(uuid_path)

        self._taxonomy_builder.save_taxonomy_artifact(
            taxonomy_artifact,
            taxonomy_path,
        )
