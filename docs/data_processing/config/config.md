# `data_processing.config.config`

Reads environment variables for API endpoints, credentials, and pagination settings. Exposes two frozen dataclasses — `GermanFundingConfig` and `EuFundingConfig` — that bundle all file paths and runtime parameters for their respective funding pipelines.

## Module Constants

| Constant | Type | Default | Description |
|---|---|---|---|
| `GERMAN_FUNDING_DATA_URL` | `str` | `"https://foerderdatenbankdump.fra1.cdn.digitaloceanspaces.com/data/parquet_data.zip"` | Source ZIP URL for the German federal funding dataset. Overridden by `GERMAN_FUNDING_DATA_URL` env var. |
| `EU_API_URL` | `str` | `"https://api.tech.ec.europa.eu/search-api/prod/rest/search"` | EU Funding & Tenders Portal search endpoint. Overridden by `EU_API_URL` env var. |
| `EU_API_KEY` | `str` | `""` | API key passed as the `apiKey` query parameter. Use `"SEDIA"` for the public key. Overridden by `EU_API_KEY` env var. |
| `EU_PAGE_SIZE` | `int` | `50` | Number of records requested per EU API page. Overridden by `EU_PAGE_SIZE` env var. |
| `EU_MAX_PAGES` | `int` | `100` | Maximum number of pages to fetch per pipeline run; acts as a safety guard. Overridden by `EU_MAX_PAGES` env var. |
| `EU_REQUEST_TIMEOUT_SECONDS` | `float` | `30.0` | HTTP request timeout in seconds for EU API calls. Overridden by `EU_REQUEST_TIMEOUT_SECONDS` env var. |
| `EU_PAGE_DELAY_SECONDS` | `float` | `0.2` | Sleep duration in seconds inserted between paginated EU API requests. Overridden by `EU_PAGE_DELAY_SECONDS` env var. |

## Data Classes

### `GermanFundingConfig`

Immutable frozen dataclass bundling file paths and the download URL for the German federal funding pipeline. All paths default to a `data/` subdirectory relative to the working directory.

**Fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `data_dir` | `Path` | `Path("data")` | Base directory for all generated data artifacts. |
| `zip_url` | `str` | `GERMAN_FUNDING_DATA_URL` | Remote URL of the source ZIP archive. |
| `zip_path` | `Path` | `data/german_parquet_data.zip` | Local path where the downloaded ZIP is written. |
| `raw_parquet` | `Path` | `data/german_parquet_data.parquet` | Path where the parquet file extracted from the ZIP is written. |
| `cleaned_parquet` | `Path` | `data/german_parquet_data_cleaned.parquet` | Destination for the cleaned, HTML-stripped parquet output. |
| `uuid_parquet` | `Path` | `data/german_parquet_data_uuid.parquet` | Destination for the UUID-enriched parquet output. |
| `taxonomy_json` | `Path` | `data/taxonomy_german.json` | Destination for the versioned taxonomy contract artifact. |

### `EuFundingConfig`

Immutable frozen dataclass bundling API settings and file paths for the EU funding pipeline. API parameters are read from environment variables and default to the public endpoint.

**Fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `data_dir` | `Path` | `Path("data")` | Base directory for all generated data artifacts. |
| `api_url` | `str` | `EU_API_URL` | EU search API endpoint URL. |
| `api_key` | `str` | `EU_API_KEY` | API key passed as the `apiKey` query parameter. |
| `page_size` | `int` | `EU_PAGE_SIZE` | Number of results to request per API page. |
| `max_pages` | `int` | `EU_MAX_PAGES` | Maximum pages to fetch; pagination stops at this limit. |
| `request_timeout_seconds` | `float` | `EU_REQUEST_TIMEOUT_SECONDS` | HTTP timeout per request in seconds. |
| `page_delay_seconds` | `float` | `EU_PAGE_DELAY_SECONDS` | Sleep between consecutive page requests in seconds. |
| `raw_json` | `Path` | `data/eu_open_calls.json` | Path where freshly fetched call records are cached as JSON. |
| `cleaned_parquet` | `Path` | `data/eu_parquet_data_cleaned.parquet` | Destination for the cleaned parquet output. |
| `uuid_parquet` | `Path` | `data/eu_parquet_data_uuid.parquet` | Destination for the UUID-enriched parquet output. |
| `taxonomy_json` | `Path` | `data/taxonomy_eu.json` | Destination for the versioned taxonomy contract artifact. |
