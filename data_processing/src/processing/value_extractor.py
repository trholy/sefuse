import polars as pl
from pathlib import Path
import unicodedata
import re


class UniqueValueExtractor:
    FALLBACK = "Unknown"

    def _normalize(self, value: str) -> str:
        if value is None:
            return ""

        value = str(value).strip().lower()

        # German umlauts
        value = (
            value.replace("ä", "ae")
                 .replace("ö", "oe")
                 .replace("ü", "ue")
                 .replace("ß", "ss")
        )

        # Remove accents
        value = unicodedata.normalize("NFKD", value)
        value = "".join(c for c in value if not unicodedata.combining(c))

        # Normalize separators
        value = re.sub(r"[\s\-&/]+", "_", value)

        # Remove non-word chars
        value = re.sub(r"[^\w]", "", value)

        return value.strip("_")

    def _is_invalid(self, value: str, key: str) -> bool:
        """
        Decide if something should go to fallback bucket
        """
        if not key:
            return True

        v = str(value).strip().lower()

        # obvious null-like values
        if v in {"none", "nan", "", "null"}:
            return True

        # too short or meaningless
        if len(key) <= 2:
            return True

        return False

    def _score(self, value: str) -> int:
        if value is None:
            return -1

        v = str(value)

        score = 0

        if any(c.isupper() for c in v):
            score += 2

        if " " in v:
            score += 2

        if "_" in v:
            score -= 1

        if v.islower():
            score -= 1

        return score

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
