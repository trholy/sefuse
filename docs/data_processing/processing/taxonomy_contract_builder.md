# `data_processing.processing.taxonomy_contract_builder`

Builds canonical taxonomy mappings from dataframe values, canonicalizes category columns, and writes versioned taxonomy contract artifacts.

## Class `TaxonomyContractBuilder`

### Main Responsibilities

- Scan category columns and collect aliases by normalized key.
- Pick canonical display values per key.
- Canonicalize dataframe list/scalar values to canonical labels.
- Generate normalized `*_keys` columns.
- Build and save taxonomy JSON artifacts with deterministic hash/version metadata.

### Key Methods

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
