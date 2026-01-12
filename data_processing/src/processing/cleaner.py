from typing import Iterable
import polars as pl
from bs4 import BeautifulSoup


class HtmlCleaner:
    def clean(self, value: str | None) -> str:
        if not value:
            return "N/A"

        if "<" in value and ">" in value:
            soup = BeautifulSoup(value, "html.parser")
            return soup.get_text(separator=" ", strip=True)

        return value.strip()


class DataCleaner:
    def __init__(self, html_cleaner: HtmlCleaner):
        self._html_cleaner = html_cleaner

    def clean_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:

        df = df.with_columns([
            pl.col("description").str.extract(
                r"<h3>\s*Kurztext\s*</h3>(.*?)<h3>\s*Volltext\s*</h3>",
                1).alias("project_short_description"),
            pl.col("description").str.extract(
                r"<h3>\s*Volltext\s*</h3>(.*)$",
                1).alias("project_full_description"),
        ])

        df = df.with_columns(
            pl.col(pl.Utf8).replace("", None).fill_null("N/A")
        )

        string_columns: Iterable[str] = [
            col for col, dtype in zip(df.columns, df.dtypes) if dtype == pl.Utf8
        ]

        for col in string_columns:
            df = df.with_columns(
                pl.col(col).map_elements(
                    self._html_cleaner.clean,
                    return_dtype=pl.Utf8,
                ))

        return df
