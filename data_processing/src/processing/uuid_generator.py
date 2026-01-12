import uuid
import polars as pl


class UuidGenerator:
    def __init__(self, namespace: uuid.UUID):
        self._namespace = namespace

    def add_uuid_column(
        self,
        df: pl.DataFrame,
        source_column: str,
        target_column: str = "uuid",
    ) -> pl.DataFrame:
        return df.with_columns(
            pl.col(source_column).map_elements(
                lambda value: str(uuid.uuid5(self._namespace, value)),
                return_dtype=pl.Utf8).alias(target_column)
        )
