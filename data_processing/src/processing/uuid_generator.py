import uuid
import polars as pl


class UuidGenerator:
    """Generates deterministic UUID5 values from an existing DataFrame column.

    Args:
        namespace (uuid.UUID): UUID namespace used as the base for uuid5 generation.

    Example:
        gen = UuidGenerator(namespace=uuid.UUID("12345678-1234-5678-1234-567812345678"))
        df = gen.add_uuid_column(df, source_column="id_hash")
    """

    def __init__(self, namespace: uuid.UUID):
        self._namespace = namespace

    def add_uuid_column(
        self,
        df: pl.DataFrame,
        source_column: str,
        target_column: str = "uuid",
    ) -> pl.DataFrame:
        """Add a UUID5 column derived from an existing string column.

        Args:
            df (pl.DataFrame): Input DataFrame.
            source_column (str): Column whose values are hashed to produce UUIDs.
            target_column (str, default="uuid"): Name of the new UUID column.

        Returns:
            pl.DataFrame: DataFrame with the new UUID column appended.
        """
        return df.with_columns(
            pl.col(source_column).map_elements(
                lambda value: str(uuid.uuid5(self._namespace, value)),
                return_dtype=pl.Utf8).alias(target_column)
        )
