"""Shared clean → taxonomy → UUID → Parquet pipeline used by German and EU funding flows."""

import logging
import os
from pathlib import Path

import polars as pl

from .cleaner import DataCleaner
from .taxonomy_contract_builder import TaxonomyContractBuilder
from .uuid_generator import UuidGenerator

logger = logging.getLogger(__name__)


DEFAULT_EXPORT_COLUMNS = [
    "funding_type",
    "funding_area",
    "funding_location",
    "eligible_applicants",
]

# How much the active row count may shrink against the previous run before the write
# is refused. A truncated source (half a CSV download, a spurious empty API page)
# otherwise reaches `Pipeline._delete_removed_projects` as a set difference and takes
# the missing projects out of Qdrant.
MAX_DROP_RATIO = float(os.getenv("DATA_REFRESH_MAX_DROP_RATIO", "0.2"))


class TruncatedDatasetError(RuntimeError):
    """Raised when a refresh yields far fewer active rows than the previous one.

    Aborting before anything is written leaves the last good Parquet files and
    taxonomy artifact in place, so the embedding pipeline re-runs against them as a
    no-op instead of deleting projects that only *look* gone.
    """


def active_row_count(df: pl.DataFrame) -> int:
    """Count the rows that will be indexed, i.e. those not marked ``deleted``."""
    if "deleted" not in df.columns:
        return df.height
    return df.filter(pl.col("deleted") == False).height


def _previous_active_row_count(path: Path) -> int | None:
    """Read the active row count of a previously written Parquet file.

    Args:
        path (Path): Parquet file from the previous run.

    Returns:
        int | None: The previous active row count, or ``None`` when there is no
            readable previous file — the first run has nothing to compare against.
    """
    if not path.exists():
        return None
    try:
        frame = pl.scan_parquet(path)
        if "deleted" in frame.collect_schema().names():
            frame = frame.filter(pl.col("deleted") == False)
        return int(frame.select(pl.len()).collect().item())
    except Exception as error:
        logger.warning(
            "Could not read previous row count from %s (%s) — skipping the "
            "truncation check for this run",
            path, error,
        )
        return None


def drop_ratio(previous: int, current: int) -> float:
    """Return how far a record count fell, relative to the previous one.

    Both truncation guards compare against ``MAX_DROP_RATIO`` and quote the ratio in
    their message, but they act on it differently — this one refuses to write the
    parquet, while the EU pipeline refuses to overwrite its cached snapshot. Only the
    formula is shared; each caller keeps its own policy.

    Args:
        previous (int): Record count from the previous run.
        current (int): Record count this run produced.

    Returns:
        float: Relative drop, e.g. ``0.2`` when a fifth of the records are gone.
            ``0.0`` for a count that grew, and for a non-positive `previous`, so
            there is nothing to divide by.
    """
    if previous <= 0:
        return 0.0
    return (previous - current) / previous


def assert_not_truncated(
    new_df: pl.DataFrame,
    previous_path: Path,
    max_drop_ratio: float = MAX_DROP_RATIO,
) -> None:
    """Refuse a refresh whose active row count collapsed against the previous one.

    Args:
        new_df (pl.DataFrame): The frame about to be written.
        previous_path (Path): Parquet file written by the previous run.
        max_drop_ratio (float, default=MAX_DROP_RATIO): Largest tolerated relative
            drop. ``0.2`` allows losing a fifth of the dataset.

    Raises:
        TruncatedDatasetError: If the drop exceeds `max_drop_ratio`.
    """
    previous = _previous_active_row_count(previous_path)
    if previous is None or previous == 0:
        return

    current = active_row_count(new_df)
    ratio = drop_ratio(previous, current)
    if ratio > max_drop_ratio:
        raise TruncatedDatasetError(
            f"Refusing to write {previous_path}: active rows fell from {previous} to "
            f"{current} ({ratio:.1%} drop, limit {max_drop_ratio:.1%}). The "
            "source is most likely truncated; keeping the previous dataset."
        )
    logger.info(
        "Row count check passed for %s: %s -> %s active rows",
        previous_path.name, previous, current,
    )


def write_parquet_atomic(df: pl.DataFrame, target: Path) -> None:
    """Write `df` to `target` via a temporary file so readers never see a partial file.

    The FastAPI container reads these files on its own schedule; `write_parquet`
    truncates in place, so a reader arriving mid-write would otherwise hit a file
    with no footer.

    Args:
        df (pl.DataFrame): Frame to persist.
        target (Path): Final destination path.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.tmp")
    try:
        df.write_parquet(tmp_path)
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


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
        df_with_uuid = self._drop_uuid_collisions(df_with_uuid, source_column)

        columns_to_drop = columns_to_drop_before_store or []
        cleaned_output_df = cleaned_df.drop(columns_to_drop, strict=False)
        uuid_output_df = df_with_uuid.drop(columns_to_drop, strict=False)

        # Checked before anything is written, so a truncated refresh leaves the whole
        # previous snapshot — both Parquet files and the taxonomy — untouched.
        assert_not_truncated(uuid_output_df, uuid_path)

        data_dir.mkdir(parents=True, exist_ok=True)

        write_parquet_atomic(cleaned_output_df, cleaned_path)
        write_parquet_atomic(uuid_output_df, uuid_path)

        self._taxonomy_builder.save_taxonomy_artifact(
            taxonomy_artifact,
            taxonomy_path,
        )

    @staticmethod
    def _drop_uuid_collisions(
        df: pl.DataFrame,
        source_column: str,
        target_column: str = "uuid",
    ) -> pl.DataFrame:
        """Drop rows that share a UUID with an earlier row, loudly.

        Two rows with one UUID are two different projects writing to the same
        ``uuid5(project_uuid, "chunk_i")`` point ids in Qdrant: the winner is
        whichever embedding task finishes last, and a project producing fewer chunks
        leaves the other's surplus chunks behind under the same ``project_uuid``.

        Logged as an error rather than raised, so a single malformed row cannot stall
        an entire refresh — but it is a source-data bug and should be fixed upstream.

        Args:
            df (pl.DataFrame): Frame with a UUID column already assigned.
            source_column (str): Column the UUIDs were derived from, for the log line.
            target_column (str, default="uuid"): Name of the UUID column.

        Returns:
            pl.DataFrame: `df` with duplicate-UUID rows removed, order preserved.
        """
        deduplicated = df.unique(
            subset=target_column, keep="first", maintain_order=True
        )
        collisions = df.height - deduplicated.height
        if collisions:
            examples = (
                df.filter(df[target_column].is_duplicated())[source_column]
                .head(5)
                .to_list()
            )
            logger.error(
                "%s rows share a UUID with another row and were dropped. The "
                "'%s' values feeding them are not unique per project. Examples: %s",
                collisions, source_column, examples,
            )
        return deduplicated
