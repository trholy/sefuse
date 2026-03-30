# `data_processing.german_funding_main`

Runs the German funding data pipeline from source download to canonicalized parquet and taxonomy outputs.

## Main Responsibilities

- Loads `GermanFundingConfig`.
- Downloads and extracts the German source parquet file.
- Applies German-specific transformation.
- Invokes the shared pipeline for cleaning, canonicalization, UUID generation, and artifact export.

## Functions

### `run_german_funding_pipeline()`

Executes the end-to-end German data preparation workflow.

Workflow:

1. Create configuration, downloader, and extractor instances.
2. Download the archive referenced by `config.zip_url`.
3. Extract `data.parquet` into the configured raw parquet location.
4. Read the parquet file with Polars.
5. Normalize dataset columns with `GermanFundingProcessor`.
6. Pass the result to `CommonDataPipeline.process_and_store(...)`.

## Notes

- Uses `taxonomy_path=getattr(config, "taxonomy_json", None)` to keep compatibility with lightweight test stubs that may not define `taxonomy_json`.

## Outputs

- Downloaded ZIP archive.
- Extracted raw parquet file.
- Cleaned parquet file.
- UUID-enriched parquet file (including taxonomy key columns when taxonomy is enabled).
- Filter text files in the configured data directory.
- `taxonomy_german.json` contract artifact when taxonomy output is configured.
