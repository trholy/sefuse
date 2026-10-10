"""German-funding-specific processing hook for column normalisation."""

import polars as pl


class GermanFundingProcessor:
    """German-funding-specific processing hook.

    ``GermanFundingCsvParser`` already produces the target structure, including
    ``project_short_description`` and ``project_full_description``. This processor
    only maps the one column whose source name differs from the shared schema.
    """

    @staticmethod
    def transform(df: pl.DataFrame) -> pl.DataFrame:
        """Rename ``absent`` to the shared schema's ``deleted``.

        ``absent`` is upstream's name for "no longer in the export" — renamed from
        "deleted" there because absence has several causes (the programme ended, was
        reorganised, or upstream restructured their data). Downstream,
        ``Pipeline._delete_removed_projects`` keys off ``deleted`` to drop stale
        points from Qdrant.

        Args:
            df (pl.DataFrame): Raw German funding DataFrame with an ``absent`` column.

        Returns:
            pl.DataFrame: DataFrame with ``absent`` renamed to ``deleted``.
        """
        return df.rename({"absent": "deleted"})
