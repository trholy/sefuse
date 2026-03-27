# `data_processing.german_funding_main`

Runs the German funding data pipeline from file download to cleaned parquet exports.

## Main Responsibilities

- Loads `GermanFundingConfig`.
- Downloads a ZIP archive containing the source parquet file.
- Extracts `data.parquet` from the archive.
- Applies the German-specific transformation step.
- Invokes the shared pipeline for cleaning, UUID generation, and export generation.

## Functions

### `run_german_funding_pipeline()`

Executes the end-to-end German data preparation workflow.

Workflow:

1. Create configuration, downloader, and extractor instances.
2. Download the archive referenced by `config.zip_url`.
3. Extract `data.parquet` into the configured raw parquet location.
4. Read the parquet file with Polars.
5. Normalize the dataset with `GermanFundingProcessor`.
6. Pass the result to `CommonDataPipeline` for shared processing and storage.

## External Dependencies

- `FileDownloader` for HTTP download of the source archive.
- `ZipExtractor` for extracting the parquet payload.
- `GermanFundingProcessor` for dataset-specific column normalization.
- `CommonDataPipeline` for downstream cleaning and output writing.

## Outputs

- Downloaded ZIP archive.
- Extracted raw parquet file.
- Cleaned parquet file.
- UUID-enriched parquet file.
- Filter text files in the configured data directory.
