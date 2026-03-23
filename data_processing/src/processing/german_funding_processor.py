import polars as pl


class GermanFundingProcessor:
    """
    German funding specific processing hook.

    The German dataset already follows the target structure before shared
    cleaning/UUID/export steps, so this processor currently acts as a
    dedicated extension point without altering rows.
    """

    @staticmethod
    def transform(df: pl.DataFrame) -> pl.DataFrame:
        return df
