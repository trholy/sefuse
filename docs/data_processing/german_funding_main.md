# `data_processing.german_funding_main`

Entry point for the German federal funding data pipeline (download → parse → process → store).

## Functions

### `run_german_funding_pipeline() -> None`

Download, parse, clean, and store the German federal funding dataset.

Orchestrates the full pipeline:

1. Builds `GermanFundingConfig` from environment-backed defaults.
2. Attempts to download the published CSV from `config.csv_url` via `FileDownloader`.
   - If the download fails **and** a local file already exists at `config.csv_path`, logs a warning and continues with the cached file.
   - If the download fails and no local file exists, raises `RuntimeError` with instructions to place the CSV manually.
3. Parses the CSV into a Polars DataFrame via `GermanFundingCsvParser`.
4. Renames `absent` → `deleted` via `GermanFundingProcessor.transform`.
5. Runs `CommonDataPipeline.process_and_store` to clean HTML, canonicalise taxonomy columns, assign UUIDs, and write Parquet files plus the taxonomy JSON.

Invoked by the FastAPI APScheduler cron job and on startup.

!!! note "Manual seeding"
    If `https://fdb.cdl.correlaid.org/data/programme.csv` is unreachable, place the CSV manually at the host path that maps to `config.csv_path` (default: `./data/funding_data/german_programme.csv`). The pipeline reuses the cached file on the next run, so an upstream outage degrades to stale data rather than a failed refresh.

!!! info "Source and licence"
    The dataset is published by CorrelAid from the BMWE XML export and is licensed CC BY-ND 4.0 with the Bundesministerium für Wirtschaft und Energie as rights holder. Each row carries its own attribution in `license_info`; the German search page shows a source credit below its results.

**Returns:** `None`

## Outputs

| Artifact | Path (from `GermanFundingConfig`) | Description |
|---|---|---|
| CSV export | `csv_path` | Downloaded source CSV from CorrelAid's published distribution. |
| Cleaned Parquet | `cleaned_parquet` | HTML-stripped, normalised funding records. |
| UUID Parquet | `uuid_parquet` | Cleaned records enriched with deterministic UUID column and taxonomy key columns. |
| Taxonomy JSON | `taxonomy_json` | Versioned taxonomy contract (`taxonomy_german.json`). |
