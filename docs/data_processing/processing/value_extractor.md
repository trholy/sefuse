# `data_processing.processing.value_extractor`

Extracts deduplicated canonical taxonomy values from funding DataFrames.

---

## Class `UniqueValueExtractor`

Extracts a deduplicated, best-display-form list of taxonomy values from a DataFrame column.

Values that normalise to an invalid key (too short, null-like) are replaced with `FALLBACK = "Unknown"`. Among aliases sharing the same normalised key, the highest-scored display form (mixed-case, spaced) is kept.

### Class Constant

| Constant | Type | Value | Description |
|---|---|---|---|
| `FALLBACK` | `str` | `"Unknown"` | Appended to the result list when any invalid taxonomy values were encountered. |

---

### `_normalize(value: str) -> str`

Return the normalised taxonomy key for `value` via `normalize_taxonomy_key`.

**Parameters:**

- `value` (`str`): Raw taxonomy string.

**Returns:** `str` — Normalised key (ASCII-folded, lowercased, underscored).

---

### `_is_invalid(value: str, key: str) -> bool`

Return `True` when `value`/`key` should fall back to the fallback bucket.

**Parameters:**

- `value` (`str`): Original raw string.
- `key` (`str`): Normalised key from `_normalize`.

**Returns:** `bool`

---

### `_score(value: str) -> int`

Return a display-quality score for `value` (higher is better).

**Parameters:**

- `value` (`str`): Candidate display string.

**Returns:** `int` — Score from `score_taxonomy_display_value`; mixed-case spaced strings score higher.

---

### `extract(df: pl.DataFrame, column: str) -> list[str]`

Return a sorted, deduplicated list of canonical taxonomy values from a column.

Supports both scalar string columns and list-typed columns (exploded before processing). For each normalised key the alias with the highest display-quality score is kept. `FALLBACK` is appended if any invalid values were encountered.

**Parameters:**

- `df` (`pl.DataFrame`): DataFrame containing the column to scan.
- `column` (`str`): Name of the column (scalar or list dtype) to extract values from.

**Returns:** `list[str]` — Sorted unique canonical values, with `FALLBACK` appended if any invalid values were found.

---

### `save(values: list[str], target_path: Path) -> None`

Write values to a plain-text file, one value per line.

**Parameters:**

- `values` (`list[str]`): Values to persist.
- `target_path` (`Path`): Destination file path.

**Returns:** `None`
