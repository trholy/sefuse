"""Shared clean → taxonomy → UUID → Parquet pipeline used by German and EU funding flows."""

from pathlib import Path

import polars as pl

from .cleaner import DataCleaner
from .taxonomy_contract_builder import TaxonomyContractBuilder
from .uuid_generator import UuidGenerator


DEFAULT_EXPORT_COLUMNS = [
    "funding_type",
    "funding_area",
    "funding_location",
    "eligible_applicants",
]


class CommonDataPipeline:
    """Shared processing pipeline: clean → canonicalise taxonomy → assign UUIDs → save Parquet.

    Used by both the German and EU funding pipelines to avoid code duplication.
    Taxonomy canonicalisation is handled by `TaxonomyContractBuilder`; a default
    instance is created if none is provided.

    Args:
        cleaner (DataCleaner): Cleans HTML and normalises string columns.
        uuid_generator (UuidGenerator): Derives UUIDs from a source column.
        taxonomy_builder (TaxonomyContractBuilder | None, default=None): Builds and
            saves the taxonomy contract. A fresh instance is created when omitted.

    Example:
        pipeline = CommonDataPipeline(cleaner=DataCleaner(HtmlCleaner()), uuid_generator=gen)
        pipeline.process_and_store(df, cleaned_path, uuid_path, source_column="id_hash",
                                   data_dir=Path("data"), taxonomy_path=Path("data/taxonomy.json"))
    """

    def __init__(
        self,
        cleaner: DataCleaner,
        uuid_generator: UuidGenerator,
        taxonomy_builder: TaxonomyContractBuilder | None = None,
    ):
        """Initialise a CommonDataPipeline with its collaborator objects.

        Args:
            cleaner (DataCleaner): Cleans HTML and normalises string columns.
            uuid_generator (UuidGenerator): Derives UUIDs from a source column.
            taxonomy_builder (TaxonomyContractBuilder | None, optional): Builds and
                saves the taxonomy contract. A fresh instance is created when ``None``.
                Defaults to None.
        """
        self._cleaner = cleaner
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
        columns_to_drop_before_store: list[str] | None = None,
        taxonomy_domain: str = "german",
    ) -> None:
        """Run the full clean → taxonomy → UUID → write pipeline and save outputs.

        Writes three artefacts to disk:
        - Cleaned Parquet (without UUIDs) at `cleaned_path`.
        - UUID Parquet (with UUID column) at `uuid_path`.
        - Taxonomy JSON artifact at `taxonomy_path`.

        Args:
            df (pl.DataFrame): Raw or pre-processed input DataFrame.
            cleaned_path (Path): Destination for the cleaned Parquet file.
            uuid_path (Path): Destination for the UUID-enriched Parquet file.
            source_column (str): Column whose values are hashed to generate UUIDs.
            data_dir (Path): Root data directory; created if absent.
            taxonomy_path (Path): Destination for the taxonomy JSON artifact.
            export_columns (list[str] | None, default=None): Taxonomy columns to
                canonicalise. Defaults to `DEFAULT_EXPORT_COLUMNS`.
            columns_to_drop_before_store (list[str] | None, default=None): Columns
                to remove from both output Parquet files before writing.
            taxonomy_domain (str, default="german"): Domain label embedded in the
                taxonomy artifact (`"german"` or `"eu"`).
        """
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

        uuid_path.parent.mkdir(parents=True, exist_ok=True)
        uuid_output_df.write_parquet(uuid_path)

        self._taxonomy_builder.save_taxonomy_artifact(
            taxonomy_artifact,
            taxonomy_path,
        )
