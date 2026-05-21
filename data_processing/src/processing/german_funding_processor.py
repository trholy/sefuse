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
        """Rename German-specific date columns to the shared `date_1`/`date_2` schema.

        Args:
            df (pl.DataFrame): Raw German funding DataFrame with `on_website_from`
                and `last_updated` columns.

        Returns:
            pl.DataFrame: DataFrame with columns renamed to `date_1` and `date_2`.
        """
        df = df.rename({
            "on_website_from": "date_1",
            "last_updated": "date_2"
        })
        return df
