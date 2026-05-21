# `data_processing.processing.taxonomy_contract_builder`

Builds canonical taxonomy mappings from dataframe values, canonicalizes category columns, and writes versioned taxonomy contract artifacts.

## Class `TaxonomyContractBuilder`

### Main Responsibilities

- Scan category columns and collect aliases by normalized key.
- Pick canonical display values per key.
- Canonicalize dataframe list/scalar values to canonical labels.
- Generate normalized `*_keys` columns.
- Build and save taxonomy JSON artifacts with deterministic hash/version metadata.

### Internal Methods

#### `_build_column_mapping(df, column)`

Builds a normalised-key-to-canonical-display mapping for one taxonomy column. Explodes list-typed columns, groups raw values by their normalised key, picks the best display name per key using `score_taxonomy_display_value`, and collects alias/count metadata for the taxonomy artifact. Returns a `(key_to_canonical, entries)` tuple.

#### `_canonicalize_list_value(value, key_to_canonical)`

Replaces raw taxonomy cell values (scalar, list, or `pl.Series`) with their canonical display names using the mapping from `_build_column_mapping`. Invalid or unrecognised values fall back to `TAXONOMY_FALLBACK_VALUE`. Duplicates are removed while preserving order.

#### `_keys_for_value(value)`

Converts raw taxonomy cell values (scalar, list, or `pl.Series`) to their normalised lookup keys via `normalize_taxonomy_key`. Duplicates are removed while preserving order.

### Public Methods

#### `canonicalize_dataframe(df, columns)`

Returns:

- Canonicalized dataframe (category columns normalized to canonical labels).
- Taxonomy column metadata (`key`, `canonical`, `aliases`, `count`).

#### `build_taxonomy_artifact(domain, columns)`

Builds a taxonomy contract dictionary containing:

- `domain`
- `generated_at_utc`
- `version`
- `hash`
- `columns`

#### `save_taxonomy_artifact(taxonomy, target_path)`

Writes the taxonomy contract as UTF-8 JSON.
