# `fastapi.main`

Defines the FastAPI application, startup jobs, scheduled refresh workflows, taxonomy endpoint, and funding search endpoints.

## Main Responsibilities

- Fail-fast at import: calls `sys.exit(1)` when `INTERNAL_API_TOKEN` is empty and `ALLOW_UNAUTHENTICATED_INTERNAL_API` is not set, or when the token starts with `change_me`.
- Gates all non-health endpoints behind a shared-secret `X-Internal-Token` header via `InternalTokenMiddleware`.
- Disables the public `/docs`, `/redoc`, and `/openapi.json` documentation endpoints.
- Applies per-IP rate limiting via `slowapi` (30 req/min on search endpoints, 120 req/min on vocab).
- Starts German and EU data-processing jobs on application startup in parallel with the Ollama model readiness probe.
- Starts embedding refresh pipelines on startup and cron schedule.
- Exposes REST endpoints for German/EU search, taxonomy retrieval, and health checking.

---

## Startup Guards

At module import time the following checks are applied in order:

1. If `INTERNAL_API_TOKEN` is empty and `ALLOW_UNAUTHENTICATED_INTERNAL_API` is not set → logs a critical banner and calls `sys.exit(1)`.
2. If `INTERNAL_API_TOKEN` is empty but the bypass flag is set → `logger.warning` (no error).
3. If `INTERNAL_API_TOKEN` starts with `change_me` → logs a critical banner and calls `sys.exit(1)`.

---

## Module Constants

| Constant | Type | Default | Description |
|---|---|---|---|
| `INTERNAL_API_TOKEN` | `str` | `""` | Shared secret read from the `INTERNAL_API_TOKEN` env var. |
| `OLLAMA_URL` | `str` | `"http://ollama:11434"` | Base URL of the Ollama embedding service. |
| `EMBED_MODEL` | `str` | `"bge-m3"` | Ollama model name used for query embedding. |
| `TOKENIZER` | `str` | `"BAAI/bge-m3"` | HuggingFace tokenizer identifier. |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `float` | `120.0` | Per-request HTTP timeout for embedding calls. |
| `TOPK_SCORES` | `int` | `3` | Number of top chunk scores averaged per project during aggregation. |
| `OLLAMA_MODEL_READY_INTERVAL` | `int` | `10` | Seconds between model readiness probe retries. |
| `OLLAMA_MODEL_READY_TIMEOUT` | `int` | `600` | Maximum seconds to wait for Ollama model readiness before skipping embedding pipelines. |
| `RUN_STARTUP_PIPELINES_SYNC` | `bool` | `False` | When `True`, startup blocks until all pipelines complete. |
| `GERMAN_COLLECTION_NAME` | `str` | `"fundings_german"` | Qdrant collection name for German funding data. |
| `EU_COLLECTION_NAME` | `str` | `"fundings_eu"` | Qdrant collection name for EU funding data. |
| `GERMAN_EXTRACTED_FILE_PATH` | `str` | `"data/german_parquet_data_uuid.parquet"` | Path to UUID-enriched German Parquet file. |
| `EU_EXTRACTED_FILE_PATH` | `str` | `"data/eu_parquet_data_uuid.parquet"` | Path to UUID-enriched EU Parquet file. |
| `GERMAN_TAXONOMY_FILE_PATH` | `str` | `"data/taxonomy_german.json"` | Path to German taxonomy contract artifact. |

---

## Middleware

### Class `InternalTokenMiddleware`

Starlette middleware that validates a shared secret on every non-health request. Reads the expected token from `INTERNAL_API_TOKEN`. When set, every incoming request (except `GET /health`) must carry a matching `X-Internal-Token` header; mismatches receive a 403 response. Uses `hmac.compare_digest` for constant-time comparison. No-op when `INTERNAL_API_TOKEN` is empty (bypass mode for local development).

#### `dispatch(request: Request, call_next) -> Response`

Forward the request when the token matches; return 403 otherwise.

**Parameters:**

- `request` (`Request`): Incoming Starlette request.
- `call_next` (callable): Next middleware or route handler in the chain.

**Returns:** `Response` — either the downstream response or a `JSONResponse(403)`.

---

## Rate Limiting

`slowapi.Limiter` with `get_remote_address` key function:

- `/v1/search/german` and `/v1/search/eu`: **30 requests/minute** per IP.
- `/v1/vocab/german`: **120 requests/minute** per IP.

Exceeding the limit returns HTTP 429. The limiter is attached to `app.state.limiter`.

---

## Pydantic Models

### Class `SearchFilters`

Optional taxonomy filters applied server-side before returning search results. Each list field is matched with OR within the field, AND across fields. All list elements exceeding 64 characters are silently dropped; lists are capped at 50 items.

**Fields:**

- `funding_type` (`list[str] | None`, default `None`): Funding type taxonomy keys to filter on (e.g. `["Zuschuss"]`).
- `funding_area` (`list[str] | None`, default `None`): Funding area taxonomy keys.
- `funding_location` (`list[str] | None`, default `None`): Funding location taxonomy keys.
- `eligible_applicants` (`list[str] | None`, default `None`): Eligible applicant taxonomy keys.
- `drop_na` (`bool`, default `False`): When `True`, exclude results where both short and full description are `"N/A"`.

---

### Class `SearchMessage`

A single chat-style message carrying the user's search query.

**Fields:**

- `role` (`Literal["user"]`, default `"user"`): Message role; only `"user"` is accepted.
- `content` (`str`, min_length=1, max_length=5000): Search query text.

---

### Class `SearchRequest`

Validated request body for all search endpoints. FastAPI automatically rejects violations with HTTP 422 before the route handler is called.

**Fields:**

- `messages` (`list[SearchMessage]`, min_length=1, max_length=8): Conversation messages; the first item's `content` is used as the query.
- `model` (`str`): Ollama model name for query embedding, e.g. `"bge-m3"`.
- `limit` (`int`, ge=1, le=100, default=`20`): Maximum results to return.
- `semantic_weight` (`float`, ge=0.0, le=1.0, default=`0.7`): Hybrid search weight (0 = pure keyword, 1 = pure semantic).
- `filters` (`SearchFilters`, default=`SearchFilters()`): Optional taxonomy filters.

---

### Class `SearchMatch`

One aggregated project result. Scores are normalised to `[0, 1]` relative to the top result.

**Fields:**

- `project_id` (`str`): UUID of the funding project.
- `project_title` (`str`): Human-readable project title.
- `project_short_description` (`str`): Short summary.
- `project_full_description` (`str`): Full description text.
- `date_1` (`str`): First relevant date string (e.g. application deadline).
- `date_2` (`str`): Second relevant date string (e.g. last-updated date).
- `funding_type` (`list[str]`): Human-readable funding type labels.
- `funding_area` (`list[str]`): Human-readable funding area labels.
- `funding_location` (`list[str]`): Human-readable funding location labels.
- `eligible_applicants` (`list[str]`): Human-readable eligible applicant labels.
- `funding_type_keys` (`list[str]`): Normalised taxonomy keys for `funding_type`.
- `funding_area_keys` (`list[str]`): Normalised taxonomy keys for `funding_area`.
- `funding_location_keys` (`list[str]`): Normalised taxonomy keys for `funding_location`.
- `eligible_applicants_keys` (`list[str]`): Normalised taxonomy keys for `eligible_applicants`.
- `project_website` (`str`): URL of the funding program's detail page.
- `matching_score` (`float`): Relevance score normalised to `[0, 1]`.

---

### Class `SearchResponse`

Top-level response wrapper returned by the search endpoints.

**Fields:**

- `matches` (`list[SearchMatch]`): Ordered list of matching projects sorted by descending `matching_score`.

---

## Helper Functions

### `_normalize_list_field(value: Any) -> list[Any]`

Wrap a scalar in a list; return lists unchanged; return `[]` for `None`.

**Parameters:**

- `value` (`Any`): Scalar, list, or `None`.

**Returns:** `list[Any]`

---

### `_normalize_filter_keys(filters: SearchFilters) -> dict[str, set[str]]`

Convert a `SearchFilters` object to normalised taxonomy key sets.

**Parameters:**

- `filters` (`SearchFilters`): Filter model from the request body.

**Returns:** `dict[str, set[str]]` — mapping from field name to its set of normalised taxonomy keys. Fields with no selected values are omitted.

---

### `_result_matches_filters(result: dict[str, Any], filter_keys: dict[str, set[str]]) -> bool`

Return `True` if a result satisfies all active taxonomy filters (AND across fields, OR within each field).

**Parameters:**

- `result` (`dict[str, Any]`): Aggregated result dict from `_aggregate_results`.
- `filter_keys` (`dict[str, set[str]]`): Normalised key sets from `_normalize_filter_keys`.

**Returns:** `bool`

---

### `_aggregate_results(results: list[Any]) -> list[dict[str, Any]]`

Deduplicate Qdrant chunk-level results by project using TopK-Avg scoring.

Groups by `project_uuid` from the point payload (falls back to the raw point ID for legacy points). Uses `heapq.nlargest(TOPK_SCORES, ...)` per project. The final score is the average of the top-K chunk scores.

**Parameters:**

- `results` (`list[Any]`): Raw `ScoredPoint` list from `QdrantManager.search`.

**Returns:** `list[dict[str, Any]]` — deduplicated result dicts each containing a `matching_score` field.

---

### `_await_ollama_model(client: httpx.AsyncClient) -> None`

Block until the Ollama embedding model is ready to serve requests.

Sends a test embed request every `OLLAMA_MODEL_READY_INTERVAL` seconds, retrying on 404 (model still pulling) and connection errors.

**Parameters:**

- `client` (`httpx.AsyncClient`): Shared HTTP client from `app.state`.

**Returns:** `None`

**Raises:** `TimeoutError` — if the model is not ready within `OLLAMA_MODEL_READY_TIMEOUT` seconds.

---

### `_embed_query(query: str, model: str, client: httpx.AsyncClient) -> list[float]`

Fetch a dense embedding vector for a search query from the Ollama API.

Retries once on `httpx.ConnectError`. Maps all Ollama failures to HTTP 503.

**Parameters:**

- `query` (`str`): User's search text.
- `model` (`str`): Ollama model name, e.g. `"bge-m3"`.
- `client` (`httpx.AsyncClient`): Shared HTTP client from `app.state`.

**Returns:** `list[float]` — dense embedding vector.

**Raises:** `HTTPException(503)` — when Ollama is unavailable or returns a non-2xx response.

---

### `_search_collection(body: SearchRequest, qdrant_manager: QdrantManager, client: httpx.AsyncClient) -> dict[str, Any]`

Core search handler: embed query → hybrid search → aggregate chunks → normalise scores → apply filters → sort.

**Parameters:**

- `body` (`SearchRequest`): Validated search request.
- `qdrant_manager` (`QdrantManager`): Collection to search against.
- `client` (`httpx.AsyncClient`): Shared HTTP client for embedding calls.

**Returns:** `dict[str, Any]` — `{"matches": [<result_dict>, ...]}` ready for JSON serialisation.

---

### `_load_taxonomy(path: str) -> dict[str, Any]`

Load a taxonomy JSON artifact from disk. Returns a blank skeleton on missing or malformed files.

**Parameters:**

- `path` (`str`): File path to the taxonomy JSON produced by `TaxonomyContractBuilder`.

**Returns:** `dict[str, Any]` — parsed taxonomy dict, or `{"domain": "german", "generated_at_utc": "", "version": "", "hash": "", "columns": {}}` on failure.

---

### `lifespan(app: FastAPI)`

FastAPI lifespan context manager handling startup and shutdown.

**Startup sequence:**

1. Creates `app.state.http_client` (`httpx.AsyncClient` with connection limits and `OLLAMA_EMBED_TIMEOUT_SECONDS` timeout).
2. Runs German and EU data-processing pipelines **in parallel** with the Ollama model readiness probe.
3. Starts both embedding pipelines only after both data processing and model readiness complete. If the model is not ready within `OLLAMA_MODEL_READY_TIMEOUT`, embedding pipelines are skipped gracefully.
4. Registers four APScheduler cron jobs (German/EU data processing, German/EU embedding).
5. Starts the scheduler.

**Shutdown sequence:**

1. Cancels any still-running startup background task.
2. Shuts down the scheduler (`wait=False`).
3. Closes `app.state.http_client`.

**Parameters:**

- `app` (`FastAPI`): The FastAPI application instance.

---

## API Endpoints

### `GET /health`

Returns `{"status": "ok"}` when both Qdrant managers have an initialized client; HTTP 503 with `{"status": "unavailable"}` otherwise. Exempt from `InternalTokenMiddleware`. Used by the Docker `HEALTHCHECK`.

---

### `POST /v1/search/german`

Search the German funding collection and return ranked matches. Rate-limited to 30 req/min per IP. Delegates to `_search_collection` with `german_qdrant_manager`.

**Request body:** `SearchRequest`

**Response:** `SearchResponse` (HTTP 200)

---

### `POST /v1/search/eu`

Search the EU funding collection and return ranked matches. Rate-limited to 30 req/min per IP. Delegates to `_search_collection` with `eu_qdrant_manager`.

**Request body:** `SearchRequest`

**Response:** `SearchResponse` (HTTP 200)

---

### `GET /v1/vocab/german`

Return the current German taxonomy contract artifact loaded from `taxonomy_german.json`. Returns a blank skeleton instead of an error when the file is missing or malformed. Rate-limited to 120 req/min per IP.

**Response:** `dict` with `domain`, `generated_at_utc`, `version`, `hash`, and `columns` keys.
