# `fastapi.main`

Defines the FastAPI application, startup jobs, scheduled refresh workflows, taxonomy endpoint, and funding search endpoints.

## Main Responsibilities

- Configures runtime settings for embeddings, collections, parquet paths, and taxonomy file path.
- Gates all endpoints behind a shared-secret `X-Internal-Token` header via `InternalTokenMiddleware`.
- Disables the public `/docs`, `/redoc`, and `/openapi.json` documentation endpoints.
- Starts German and EU data-processing jobs on application startup.
- Starts embedding refresh pipelines on startup and cron schedule.
- Exposes REST endpoints for German/EU search and German taxonomy retrieval.
- Aggregates chunk-level Qdrant matches into project-level responses.
- Applies key-based taxonomy filters on search results.

## Middleware

### `InternalTokenMiddleware`

Starlette middleware that validates a shared secret on every request. Reads the expected token from the `INTERNAL_API_TOKEN` environment variable. When set, every incoming request must carry a matching `X-Internal-Token` header; mismatches receive a 403 response. Uses `hmac.compare_digest` for constant-time comparison. When the variable is empty the middleware is a no-op.

## Pydantic Models

### `SearchMessage`

- `content` (str): Text content of one message.

### `SearchRequest`

Validated request body for all search endpoints.

- `messages` (list[SearchMessage], min_length=1): At least one message; the first message's `content` is used as the query.
- `model` (str): Embedding model name.
- `limit` (int, ge=1, le=200, default=20): Maximum number of results to return.
- `semantic_weight` (float, ge=0.0, le=1.0, default=0.7): Hybrid search weight (0=keyword, 1=semantic).
- `filters` (dict, default={}): Optional taxonomy filters and drop-N/A flag.

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

### `_embed_query(query, model)`

Fetches a dense embedding vector for the search query from the Ollama API.

### `_search_collection(body, qdrant_manager)`

Embeds the query from a validated `SearchRequest`, runs hybrid search, aggregates chunk-level results by project, normalizes scores to [0, 1], and applies taxonomy filters and drop-N/A.

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
