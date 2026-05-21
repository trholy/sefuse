import polars as pl
from pathlib import Path

from shared.taxonomy_contract import (
    is_invalid_taxonomy_value,
    normalize_taxonomy_key,
    score_taxonomy_display_value,
)


class UniqueValueExtractor:
    FALLBACK = "Unknown"

    def _normalize(self, value: str) -> str:
        return normalize_taxonomy_key(value)

    def _is_invalid(self, value: str, key: str) -> bool:
        """
        Decide if something should go to fallback bucket
        """
        return is_invalid_taxonomy_value(value, key)

    def _score(self, value: str) -> int:
        return score_taxonomy_display_value(value)

    def extract(self, df: pl.DataFrame, column: str) -> list[str]:
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
        target_path.write_text("\n".join(values), encoding="utf-8")
