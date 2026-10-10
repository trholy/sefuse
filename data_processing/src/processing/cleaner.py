"""HTML cleaning and DataFrame normalisation utilities for funding data pipelines."""

from typing import Iterable
import polars as pl
from bs4 import BeautifulSoup


class HtmlCleaner:
    """Strips HTML tags from a string, returning plain text."""

    def clean(self, value: str | None) -> str:
        """Strip HTML markup and return plain text.

        Args:
            value (str | None): Raw string, optionally containing HTML tags.

        Returns:
            str: Plain text with tags removed, or "N/A" for empty/None input.
        """
        if not value:
            return "N/A"

        if "<" in value and ">" in value:
            soup = BeautifulSoup(value, "html.parser")
            return soup.get_text(separator=" ", strip=True)

        return value.strip()


class DataCleaner:
    """Cleans a raw funding DataFrame: fills nulls and strips HTML from string columns.

    German-specific description extraction (Kurztext/Volltext) is performed
    upstream by ``GermanFundingProcessor.transform()``, not here.

    Args:
        html_cleaner (HtmlCleaner): Instance used to strip HTML from string columns.

    Example:
        cleaner = DataCleaner(HtmlCleaner())
        clean_df = cleaner.clean_dataframe(raw_df)
    """

    def __init__(self, html_cleaner: HtmlCleaner):
        """Initialise a DataCleaner backed by `html_cleaner`.

        Args:
            html_cleaner (HtmlCleaner): Instance used to strip HTML from string columns.
        """
        self._html_cleaner = html_cleaner

    def clean_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply generic cleaning steps to a funding DataFrame.

        Replaces empty strings with "N/A" and strips HTML from all string
        columns. German-specific description extraction (Kurztext/Volltext)
        is handled upstream by `GermanFundingProcessor.transform()`.

        Args:
            df (pl.DataFrame): Input DataFrame, already containing
                `project_short_description` and `project_full_description`
                columns if applicable.

        Returns:
            pl.DataFrame: Cleaned DataFrame with HTML stripped and nulls filled.
        """
        df = df.with_columns(
            pl.col(pl.Utf8).replace("", None).fill_null("N/A")
        )

        string_columns: Iterable[str] = [
            col for col, dtype in zip(df.columns, df.dtypes) if dtype == pl.Utf8
        ]

        for col in string_columns:
            df = df.with_columns(
                pl.when(pl.col(col).str.contains("<"))
                .then(
                    pl.col(col).map_elements(
                        self._html_cleaner.clean,
                        return_dtype=pl.Utf8,
                    )
                )
                .otherwise(pl.col(col))
                .alias(col)
            )

        return df
