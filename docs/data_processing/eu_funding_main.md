# `data_processing.eu_funding_main`

Coordinates the EU funding ingestion flow from API retrieval through transformation and shared export steps.

## Main Responsibilities

- Builds `EuFundingConfig` from environment-backed defaults.
- Fetches EU call data from the remote API, with cached-file fallback on request failures.
- Transforms raw API payloads into the shared funding schema.
- Runs shared cleaning, UUID generation, parquet persistence, and filter-value exports.

## Functions

### `_load_or_fetch_open_calls(config, fetcher)`

Retrieves EU open and forthcoming calls through `EuFundingFetcher`.

- Tries the live API first.
- Persists successful responses to `config.raw_json`.
- Falls back to the cached JSON file when the API call fails and a cache already exists.

Returns a `list[dict]` of call records.

### `run_eu_funding_pipeline()`

Executes the end-to-end EU processing pipeline.

Workflow:

1. Create configuration and API fetcher instances.
2. Load or fetch EU call data.
3. Transform raw records with `EuFundingProcessor`.
4. Clean and enrich the dataset through `CommonDataPipeline`.
5. Write cleaned and UUID-enriched parquet outputs.
6. Export unique values for selected filter columns such as `funding_area`.

## External Dependencies

- `requests` for API error handling.
- `EuFundingFetcher` for remote data access and local caching.
- `EuFundingProcessor` for EU-specific normalization.
- `CommonDataPipeline` for shared storage and export behavior.

## Outputs

- Cached raw JSON at the configured `raw_json` path.
- Cleaned parquet file at `cleaned_parquet`.
- UUID-enriched parquet file at `uuid_parquet`.
- Text exports for configured filter columns in the data directory.
