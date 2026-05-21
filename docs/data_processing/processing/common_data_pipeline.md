# `data_processing.processing.common_data_pipeline`

Implements the shared post-processing workflow used by both funding ingestion pipelines.

## Module Constant

- `DEFAULT_EXPORT_COLUMNS`: default category columns exported to text files.

## Class `CommonDataPipeline`

Combines dataframe cleaning, taxonomy canonicalization, UUID generation, and parquet storage.

### Constructor

- `cleaner`: `DataCleaner` instance.
- `uuid_generator`: `UuidGenerator` instance.
- `taxonomy_builder`: optional `TaxonomyContractBuilder` instance; defaults to an internal instance.

### `process_and_store(...)`

Processes a dataframe and writes downstream artifacts.

#### Parameters

- `df`: input `polars.DataFrame`.
- `cleaned_path`: target path for the cleaned parquet file.
- `uuid_path`: target path for the UUID-enriched parquet file.
- `source_column`: source column used to derive stable UUID values.
- `data_dir`: root data directory; created if absent.
- `export_columns`: optional list of columns to canonicalize; falls back to `DEFAULT_EXPORT_COLUMNS`.
- `export_file_prefix`: unused prefix kept for API compatibility.
- `columns_to_drop_before_store`: optional columns removed before parquet persistence.
- `taxonomy_path`: required output path for a taxonomy contract JSON artifact.
- `taxonomy_domain`: taxonomy domain label used in the contract artifact (`"german"` or `"eu"`).

#### Behavior

- Cleans the dataframe and writes cleaned and UUID-enriched parquet outputs.
- Taxonomy contract flow:
  - Canonicalizes configured category columns.
  - Adds normalized `*_keys` columns for key-based filtering.
  - Builds and writes a versioned taxonomy contract artifact to `taxonomy_path`.
