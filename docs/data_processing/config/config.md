# `data_processing.config.config`

Defines immutable configuration objects and environment-backed defaults for the data-processing pipelines.

## Module Constants

- `GERMAN_FUNDING_DATA_URL`: source ZIP URL for German funding data.
- `EU_API_URL`: EU search API endpoint.
- `EU_API_KEY`: API key used for EU search requests.
- `EU_PAGE_SIZE`: number of records requested per EU API page.
- `EU_MAX_PAGES`: maximum page count fetched from the EU API.
- `EU_REQUEST_TIMEOUT_SECONDS`: HTTP timeout for EU requests.
- `EU_PAGE_DELAY_SECONDS`: delay between EU page requests.

## Data Classes

### `GermanFundingConfig`

Immutable configuration for the German pipeline.

Important fields:

- `data_dir`: base directory for generated data artifacts.
- `zip_url`: remote source archive.
- `zip_path`: local ZIP download target.
- `raw_parquet`: extracted parquet file path.
- `cleaned_parquet`: cleaned output path.
- `uuid_parquet`: UUID-enriched output path.
- `taxonomy_json`: taxonomy contract output path (`taxonomy_german.json`).

### `EuFundingConfig`

Immutable configuration for the EU pipeline.

Important fields:

- `data_dir`: base directory for generated artifacts.
- `api_url`: EU API endpoint.
- `api_key`: API credential value.
- `page_size`: number of items per request page.
- `max_pages`: maximum number of pages to retrieve.
- `request_timeout_seconds`: request timeout.
- `page_delay_seconds`: delay inserted between page fetches.
- `raw_json`: cached raw API response file.
- `cleaned_parquet`: cleaned output path.
- `uuid_parquet`: UUID-enriched output path.
