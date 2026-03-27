# `data_processing.processing.common_data_pipeline`

Implements the shared post-processing workflow used by both funding ingestion pipelines.

## Module Constant

- `DEFAULT_EXPORT_COLUMNS`: default filter columns exported to text files.

## Class `CommonDataPipeline`

Combines dataframe cleaning, UUID generation, parquet storage, and filter-value extraction.

### Constructor

- `cleaner`: `DataCleaner` instance.
- `value_extractor`: `UniqueValueExtractor` instance.
- `uuid_generator`: `UuidGenerator` instance.

### `process_and_store(...)`

Processes a dataframe and writes all downstream artifacts.

#### Parameters

- `df`: input `polars.DataFrame`.
- `cleaned_path`: target path for the cleaned parquet file.
- `uuid_path`: target path for the UUID-enriched parquet file.
- `source_column`: source column used to derive stable UUID values.
- `data_dir`: directory for exported filter text files.
- `export_columns`: optional list of columns to export; falls back to `DEFAULT_EXPORT_COLUMNS`.
- `export_file_prefix`: optional filename prefix for exported text files.
- `columns_to_drop_before_store`: optional columns removed before parquet persistence.
