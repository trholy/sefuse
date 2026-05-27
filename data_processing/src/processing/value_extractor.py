"""Extracts deduplicated canonical taxonomy values from funding DataFrames."""

import polars as pl
from pathlib import Path

from shared.taxonomy_contract import (
    is_invalid_taxonomy_value,
    normalize_taxonomy_key,
    score_taxonomy_display_value,
)


class UniqueValueExtractor:
    """Extracts a deduplicated, best-display-form list of taxonomy values from a DataFrame column.

    Values that normalise to an invalid key (too short, null-like) are replaced with
    `FALLBACK = "Unknown"`. Among aliases that share the same normalised key the
    highest-scored display form (mixed-case, spaced) is kept.

    Example:
        extractor = UniqueValueExtractor()
        values = extractor.extract(df, "funding_type")
        extractor.save(values, Path("data/funding_type_values.txt"))
    """

    FALLBACK = "Unknown"

    def _normalize(self, value: str) -> str:
        """Return the normalised taxonomy key for `value`."""
        return normalize_taxonomy_key(value)

    def _is_invalid(self, value: str, key: str) -> bool:
        """Return ``True`` when `value`/`key` should fall back to the fallback bucket."""
        return is_invalid_taxonomy_value(value, key)

    def _score(self, value: str) -> int:
        """Return a display-quality score for `value` (higher is better)."""
        return score_taxonomy_display_value(value)

    def extract(self, df: pl.DataFrame, column: str) -> list[str]:
        """Return a sorted, deduplicated list of canonical taxonomy values from a column.

        Args:
            df (pl.DataFrame): DataFrame containing the column to scan.
            column (str): Name of the column (scalar or list dtype) to extract values from.

        Returns:
            list[str]: Sorted unique canonical values, with `FALLBACK` appended if any
                invalid values were encountered.
        """
        dtype = df.schema[column]

        if dtype.base_type() == pl.List:
            series = df.explode(column)[column]
        else:
            series = df[column]

        series = series.drop_nulls()

        best_values = {}
        fallback_needed = False

        for val in series.to_list():
            key = self._normalize(val)

            # fallback handling
            if self._is_invalid(val, key):
                fallback_needed = True
                continue

            if key not in best_values:
                best_values[key] = val
            else:
                if self._score(val) > self._score(best_values[key]):
                    best_values[key] = val

        result = [str(v).strip() for v in best_values.values()]

        if fallback_needed:
            result.append(self.FALLBACK)

        return sorted(set(result))

    def save(self, values: list[str], target_path: Path) -> None:
        """Write values to a plain-text file, one per line.

        Args:
            values (list[str]): Values to persist.
            target_path (Path): Destination file path.
        """
        target_path.write_text("\n".join(values), encoding="utf-8")
