# `fastapi.main`

Defines the FastAPI application, startup jobs, scheduled refresh workflows, taxonomy endpoint, and funding search endpoints.

## Main Responsibilities

- Configures runtime settings for embeddings, collections, parquet paths, and taxonomy file path.
- Gates all endpoints behind a shared-secret `X-Internal-Token` header via `InternalTokenMiddleware`.
- Disables the public `/docs`, `/redoc`, and `/openapi.json` documentation endpoints.
- Starts German and EU data-processing jobs on application startup.
- Starts embedding refresh pipelines on startup and cron schedule.
- Exposes REST endpoints for German/EU search and German taxonomy retrieval.
- Aggregates chunk-level Qdrant matches into project-level responses using TopK-Avg scoring.
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
- `limit` (int, ge=1, le=100, default=20): Maximum number of results to return.
- `semantic_weight` (float, ge=0.0, le=1.0, default=0.7): Hybrid search weight (0=keyword, 1=semantic).
- `filters` (dict, default={}): Optional taxonomy filters and drop-N/A flag.

## Module Constants

- `TOPK_SCORES` (int, default=3): Number of top chunk scores averaged per project during result aggregation.
- `OLLAMA_MODEL_READY_INTERVAL` (int, default=10): Seconds between readiness probe retries while waiting for the Ollama model to finish pulling.
- `OLLAMA_MODEL_READY_TIMEOUT` (int, default=600): Maximum seconds to wait for the Ollama model before skipping the embedding pipelines.

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

Deduplicates chunk-level vector search results by project using TopK-Avg scoring. Multiple chunks from the same project are collapsed into one entry, grouped by `project_uuid` (with fallback to `id_url`, then the raw point ID for legacy points). The final score is the average of the top-K (`TOPK_SCORES=3`) chunk scores per project, which is more robust than MaxP against single spuriously high chunk scores.

### `_await_ollama_model()`

Blocks until the Ollama embedding model is ready to serve requests. Sends a test embed request every `OLLAMA_MODEL_READY_INTERVAL` seconds, retrying on 404 (model still pulling) and connection errors. The per-request timeout uses `OLLAMA_EMBED_TIMEOUT_SECONDS` (default 120 s) rather than a short value because the first successful request triggers Ollama's model load into GPU memory, which can take over 30 s — a shorter timeout would cause Ollama to abort the load on client disconnect and restart from scratch on the next probe. Raises `TimeoutError` after `OLLAMA_MODEL_READY_TIMEOUT` seconds.

### `_embed_query(query, model)`

Fetches a dense embedding vector for the search query from the Ollama API. Uses a module-level `httpx.AsyncClient` for connection reuse across requests.

### `_search_collection(body, qdrant_manager)`

Core search handler. Pipeline: embed query → hybrid search (CC fusion) → aggregate chunks by project (TopK-Avg) → normalize scores to [0, 1] → apply taxonomy filters and drop-N/A → sort by descending score.

### `_load_taxonomy(path)`

Loads taxonomy JSON from disk and returns a safe empty taxonomy structure when unavailable.

### `lifespan(app)`

FastAPI lifespan handler that:

1. Waits for the Ollama model to be ready (`_await_ollama_model`) **in parallel** with data processing — data pipelines don't need Ollama so they run concurrently with the readiness probe.
2. Runs both embedding pipelines only after both data processing and the model readiness check have completed. If the model is not ready within the timeout, embedding pipelines are skipped gracefully.
3. Registers scheduled German and EU processing jobs with `AsyncIOScheduler`.
4. Starts and cleanly shuts down the scheduler and the shared `httpx.AsyncClient`.

## API Endpoints

### `POST /v1/search/german`

Searches the German funding collection and supports taxonomy key filters in the request body.

### `POST /v1/search/eu`

Searches the EU funding collection.

### `GET /v1/vocab/german`

Returns the current German taxonomy contract artifact loaded from `taxonomy_german.json`.
