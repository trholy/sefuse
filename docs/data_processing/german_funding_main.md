# `data_processing.german_funding_main`

Entry point for the German federal funding data pipeline (download → extract → process → store).

## Functions

### `run_german_funding_pipeline() -> None`

Download, extract, clean, and store the German federal funding dataset.

Orchestrates the full pipeline:

1. Builds `GermanFundingConfig` from environment-backed defaults.
2. Downloads the ZIP archive from `config.zip_url` via `FileDownloader`.
3. Extracts `data.parquet` from the archive via `ZipExtractor`.
4. Reads the raw parquet with Polars.
5. Renames date columns (`on_website_from` → `date_1`, `last_updated` → `date_2`) via `GermanFundingProcessor.transform`.
6. Runs `CommonDataPipeline.process_and_store` to clean HTML, canonicalise taxonomy columns, assign UUIDs, and write Parquet files plus the taxonomy JSON.

Invoked by the FastAPI APScheduler cron job and on startup.

**Returns:** `None`

## Outputs

| Artifact | Path (from `GermanFundingConfig`) | Description |
|---|---|---|
| ZIP archive | `zip_path` | Downloaded source archive from the CDN. |
| Raw Parquet | `raw_parquet` | Parquet file extracted from the ZIP. |
| Cleaned Parquet | `cleaned_parquet` | HTML-stripped, normalised funding records. |
| UUID Parquet | `uuid_parquet` | Cleaned records enriched with deterministic UUID column and taxonomy key columns. |
| Taxonomy JSON | `taxonomy_json` | Versioned taxonomy contract (`taxonomy_german.json`). |
