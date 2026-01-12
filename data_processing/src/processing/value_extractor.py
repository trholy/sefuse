import polars as pl
from pathlib import Path


class UniqueValueExtractor:
    def extract(self, df: pl.DataFrame, column: str) -> list[str]:
        dtype = df.schema[column]

        if dtype.base_type() == pl.List:
            return df.explode(column)[column].unique().to_list()

        return df[column].unique().to_list()

    def save(self, values: list[str], target_path: Path) -> None:
        target_path.write_text("\n".join(map(str, values)), encoding="utf-8")
