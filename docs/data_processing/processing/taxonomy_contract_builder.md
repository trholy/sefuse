# `data_processing.processing.taxonomy_contract_builder`

Builds and serialises the taxonomy contract: canonical display values, normalised keys, and a versioned JSON artifact consumed by the `/v1/vocab/german` endpoint.

---

## Class `TaxonomyContractBuilder`

Normalises raw taxonomy values (funding type, area, location, applicants) to canonical display names, adds `*_keys` columns, and produces a versioned JSON artifact.

---

### `_iter_values(df: pl.DataFrame, column: str) -> list[str]`

Flatten and return all non-null string values from a scalar or list-typed column.

**Parameters:**

- `df` (`pl.DataFrame`): Source DataFrame.
- `column` (`str`): Column name; list-typed columns are exploded before iterating.

**Returns:** `list[str]` — Flat list of stripped, non-null string values.

---

### `_build_column_mapping(df: pl.DataFrame, column: str) -> tuple[dict[str, str], list[dict[str, object]]]`

Build a normalised-key-to-canonical-display mapping for one taxonomy column.

Groups raw values by normalised key, picks the best display name per key using `score_taxonomy_display_value`, and collects alias/count metadata for the artifact.

**Parameters:**

- `df` (`pl.DataFrame`): Source DataFrame.
- `column` (`str`): Name of the taxonomy column to process.

**Returns:** `tuple[dict[str, str], list[dict[str, object]]]` — A mapping of normalised key to canonical display name, and a sorted list of entry dicts (`key`, `canonical`, `aliases`, `count`) for the artifact.

---

### `_canonicalize_list_value(value: object, key_to_canonical: dict[str, str]) -> list[str]`

Replace raw taxonomy values with their canonical display names.

Handles scalar, list, and `pl.Series` inputs. Invalid or unrecognised values fall back to `TAXONOMY_FALLBACK_VALUE`. Duplicates are removed while preserving insertion order.

**Parameters:**

- `value` (`object`): Raw cell value (scalar, list, `pl.Series`, or `None`).
- `key_to_canonical` (`dict[str, str]`): Normalised-key-to-canonical mapping from `_build_column_mapping`.

**Returns:** `list[str]` — Deduplicated canonical display names.

---

### `_keys_for_value(value: object) -> list[str]`

Convert raw taxonomy values to their normalised lookup keys via `normalize_taxonomy_key`.

Handles scalar, list, and `pl.Series` inputs. Duplicates are removed while preserving insertion order.

**Parameters:**

- `value` (`object`): Raw cell value (scalar, list, `pl.Series`, or `None`).

**Returns:** `list[str]` — Deduplicated normalised taxonomy keys.

---

### `canonicalize_dataframe(df: pl.DataFrame, columns: list[str]) -> tuple[pl.DataFrame, dict[str, list[dict[str, object]]]]`

Normalise taxonomy columns in-place and return the updated DataFrame plus metadata.

For each column in `columns`, maps raw values to canonical display names and adds a `<column>_keys` column with normalised lookup keys.

**Parameters:**

- `df` (`pl.DataFrame`): DataFrame containing the taxonomy columns to process.
- `columns` (`list[str]`): Names of columns to canonicalise. Columns absent from `df` are silently skipped.

**Returns:** `tuple[pl.DataFrame, dict[str, list[dict[str, object]]]]` — Updated DataFrame and a mapping of column name to its list of taxonomy entry dicts.

---

### `build_taxonomy_artifact(domain: str, columns: dict[str, list[dict[str, object]]]) -> dict[str, object]`

Build a versioned taxonomy artifact dict ready for JSON serialisation.

Computes a SHA-256 hash over the column data to produce a stable 12-character version string.

**Parameters:**

- `domain` (`str`): Domain label, e.g. `"german"` or `"eu"`.
- `columns` (`dict[str, list[dict[str, object]]]`): Mapping produced by `canonicalize_dataframe`.

**Returns:** `dict[str, object]` — Artifact with keys `domain`, `generated_at_utc`, `version` (first 12 chars of SHA-256), `hash` (full SHA-256 hex), `columns`.

---

### `save_taxonomy_artifact(taxonomy: dict[str, object], target_path: Path) -> None`

Serialise a taxonomy artifact to a UTF-8 JSON file.

**Parameters:**

- `taxonomy` (`dict[str, object]`): Artifact produced by `build_taxonomy_artifact`.
- `target_path` (`Path`): Destination file path; parent directories are created automatically.

**Returns:** `None`
