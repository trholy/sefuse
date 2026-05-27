# `data_processing.eu_funding_main`

Entry point for the EU funding data pipeline (fetch → process → store).

## Functions

### `_load_or_fetch_open_calls(config: EuFundingConfig, fetcher: EuFundingFetcher, max_pages: int | None = None) -> list[dict]`

Fetch EU calls from the API, falling back to the cached JSON on network errors.

Saves freshly fetched calls to `config.raw_json` before returning them. If the API request fails and no cache file exists, the exception is re-raised.

**Parameters:**

- `config` (`EuFundingConfig`): Pipeline configuration with API settings and file paths.
- `fetcher` (`EuFundingFetcher`): Configured fetcher instance.
- `max_pages` (`int | None`, default `None`): Maximum pages to fetch; `None` means no limit.

**Returns:** `list[dict]` — Open/forthcoming EU call records (live or cached).

**Raises:** `requests.RequestException` — If the API is unreachable and no cache file exists at `config.raw_json`.

---

### `run_eu_funding_pipeline() -> None`

Fetch, process, and store the EU funding dataset end-to-end.

Orchestrates the full EU pipeline:

1. Builds `EuFundingConfig` from environment-backed defaults.
2. Logs a `WARNING` when `config.api_key == "SEDIA"` (public key in use).
3. Fetches open/forthcoming calls via `EuFundingFetcher`, falling back to the cached JSON on network failure.
4. Transforms raw dicts to a typed Polars DataFrame via `EuFundingProcessor`.
5. Runs `CommonDataPipeline.process_and_store` to clean HTML, canonicalise the `funding_area` taxonomy, assign UUIDs, and write Parquet files plus the taxonomy JSON.

Invoked by the FastAPI APScheduler cron job and on startup.

**Returns:** `None`

## EU API Key

`SEDIA` is the publicly documented demo key for the EU Funding & Tenders Portal search API. It is sufficient for development but may have undocumented rate limits. For production deployments, set a private key via the `EU_API_KEY` environment variable.

## Outputs

| Artifact | Path (from `EuFundingConfig`) | Description |
|---|---|---|
| Raw JSON cache | `raw_json` | Freshly fetched call records saved for fallback use. |
| Cleaned Parquet | `cleaned_parquet` | HTML-stripped, normalised funding records. |
| UUID Parquet | `uuid_parquet` | Cleaned records enriched with deterministic UUID column. |
| Taxonomy JSON | `taxonomy_json` | Versioned taxonomy contract (`taxonomy_eu.json`). |
