# `fastapi.main`

Defines the FastAPI application, startup jobs, scheduled refresh workflows, taxonomy endpoint, and funding search endpoints.

## Main Responsibilities

- Configures runtime settings for embeddings, collections, parquet paths, and taxonomy file path.
- Starts German and EU data-processing jobs on application startup.
- Starts embedding refresh pipelines on startup and cron schedule.
- Exposes REST endpoints for German/EU search and German taxonomy retrieval.
- Aggregates chunk-level Qdrant matches into project-level responses.
- Applies key-based taxonomy filters on search results.

## Key Functions

### `_normalize_list_field(value)`

Ensures a payload field is always represented as a list.

### `_normalize_filter_keys(filters)`

Normalizes incoming filter payload to taxonomy key sets for:

- `funding_type`
- `funding_area`
- `funding_location`
- `eligible_applicants`

### `_result_matches_filters(result, filter_keys)`

Checks whether an aggregated result matches selected taxonomy key filters using `*_keys` payload fields.

### `_aggregate_results(results)`

Combines chunk-level vector search results by project ID and exposes both display values and `*_keys` values.

### `_search_collection(request, qdrant_manager)`

Reads search request payload, embeds query, runs vector search, aggregates results, and applies optional taxonomy filters.

### `_load_taxonomy(path)`

Loads taxonomy JSON from disk and returns a safe empty taxonomy structure when unavailable.

### `lifespan(app)`

FastAPI lifespan handler that:

1. Runs both data pipelines on startup.
2. Runs both embedding pipelines on startup.
3. Registers scheduled German and EU processing jobs with `AsyncIOScheduler`.
4. Starts and cleanly shuts down the scheduler.

## API Endpoints

### `POST /v1/search/german`

Searches the German funding collection and supports taxonomy key filters in the request body.

### `POST /v1/search/eu`

Searches the EU funding collection.

### `GET /v1/vocab/german`

Returns the current German taxonomy contract artifact loaded from `taxonomy_german.json`.
