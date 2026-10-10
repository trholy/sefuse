# `fastapi.main`

Defines the FastAPI application, startup jobs, scheduled refresh workflows, taxonomy endpoint, and funding search endpoints.

## Main Responsibilities

!!! note
    The Pydantic models and the search/alert-scoring helpers now live in
    [`utils.search_models`](utils/search_models.md) and
    [`utils.search_service`](utils/search_service.md). This page covers what is left:
    startup guards, the auth middleware, taxonomy loading, the housekeeping jobs, the
    lifespan, and the routes.

- Fail-fast at import: calls `sys.exit(1)` when `INTERNAL_API_TOKEN` is empty and `ALLOW_UNAUTHENTICATED_INTERNAL_API` is not set, or when the token starts with `change_me`.
- Gates all non-health endpoints behind a shared-secret `X-Internal-Token` header via `InternalTokenMiddleware`.
- Disables the public `/docs`, `/redoc`, and `/openapi.json` documentation endpoints.
- Applies per-IP rate limiting via `slowapi` (30 req/min on search endpoints, 120 req/min on vocab).
- Starts German and EU data-processing jobs on application startup in parallel with the Ollama model readiness probe.
- Starts embedding refresh pipelines on startup and cron schedule.
- Exposes REST endpoints for German/EU search, taxonomy retrieval, and health checking.

---

## Startup Guards

`main.py` calls `utils.startup_checks.validate_startup()` once at import, and keeps the
three values it returns as its own module attributes (`INTERNAL_API_TOKEN`,
`ALERTS_ENABLED`, `_GOTIFY_CONFIG`) — the middleware reads the token from there.

The checks, in order:

1. If `INTERNAL_API_TOKEN` is empty and `ALLOW_UNAUTHENTICATED_INTERNAL_API` is not set → banner, `sys.exit(1)`.
2. If `INTERNAL_API_TOKEN` is empty but the bypass flag is set → `logger.warning`, and startup continues.
3. If `INTERNAL_API_TOKEN` starts with `change_me` → banner, `sys.exit(1)`. Runs independently of the `QDRANT_API_KEY` checks, so a placeholder internal token is rejected even when Qdrant auth is unset, and independently of the bypass flag, which covers "no token" rather than "a token nobody replaced".
4. If `QDRANT_API_KEY` is empty → `logger.warning` (Qdrant runs unauthenticated; fine locally, set a real secret in production).
5. If `QDRANT_API_KEY` starts with `change_me` → banner, `sys.exit(1)`.
6. Gotify is resolved only when `ALERTS_ENABLED` is on, so a stale `GOTIFY_URL` cannot hold back a deployment that does not use alerts. When it is on and Gotify is enabled, the Fernet key is required up front — without it every stored token is unreadable, and the symptom would otherwise be alerts that silently never arrive.

The distinction running through all of it: a **missing** optional secret is a warning, a
**placeholder** one is fatal. Every secret in `.env.example` ships as `change_me_*`, so a
value that still starts with it means nobody replaced it.

The module has no import-time side effects — everything happens inside
`validate_startup()`. The banner is rendered by one helper rather than written out per
call site, which is why the rows now line up.

The `ALLOW_UNAUTHENTICATED_INTERNAL_API` / `RUN_STARTUP_PIPELINES_SYNC` booleans and the cron-hour env vars are parsed via the `utils.env` helpers (`read_bool`, `read_int`, `read_hour`), which fail-fast (`sys.exit(1)`) on invalid integer or out-of-range hour values. `read_bool` takes its truthy/falsy vocabulary from `shared.env.parse_bool`, which both services share; an unset variable returns the caller's default and a set-but-unreadable one reads as False.

---

## Module Constants

| Constant | Type | Default | Description |
|---|---|---|---|
| `INTERNAL_API_TOKEN` | `str` | `""` | Shared secret read from the `INTERNAL_API_TOKEN` env var. |
| `_QDRANT_API_KEY` | `str` | `""` | Qdrant API key from `QDRANT_API_KEY`; empty warns (no auth), `change_me*` exits. |
| `OLLAMA_URL` | `str` | `"http://ollama:11434"` | Base URL of the Ollama embedding service. |
| `EMBED_MODEL` | `str` | `"bge-m3"` | Ollama model name used for query embedding. |
| `TOKENIZER` | `str` | `"BAAI/bge-m3"` | HuggingFace tokenizer identifier. |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `float` | `120.0` | Per-request HTTP timeout for embedding calls. |
| `TOPK_SCORES` | `int` | `3` | Number of top chunk scores averaged per project during aggregation. |
| `ALERT_CHECK_HOUR` | `int` | `5` | Hour (UTC) of the daily saved-search alert check. |
| `ALERT_NOTIFICATION_RETENTION_DAYS` | `int` | `30` | Age at which the in-app alert inbox is pruned. |
| `_NOISE_FLOORS` | `dict[str, float]` | `{}` | Cached alert noise floor per collection name; see `collection_noise_floor`. |
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

## Helper Functions


### `_alert_score_fn(query_text, collection_type, filters, candidate_ids, *, client) -> tuple[list[dict], QueryStats]`

`AlertService`'s scoring callback: resolve the collection's noise floor, embed the saved query once, then call `alert_scores`. Module-level rather than defined inside `lifespan`, so the same path can be run in-process outside the scheduler.

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
3. Starts both embedding pipelines only after both data processing and model readiness complete. If the model is not ready within `OLLAMA_MODEL_READY_TIMEOUT`, embedding pipelines are skipped gracefully. Each embedding run invalidates its collection's cached alert noise floor.
4. Registers the APScheduler cron jobs: German/EU data processing, German/EU embedding, the saved-search alert check (`ALERT_CHECK_HOUR`), and the two Postgres housekeeping jobs from `utils.housekeeping` — `run_session_cleanup` (daily at 02:00) and `run_alert_notification_cleanup`, bound to `ALERT_NOTIFICATION_RETENTION_DAYS` via `functools.partial` at registration rather than read from a module global.
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

Search the German funding collection and return ranked matches. Rate-limited to 30 req/min per IP. Delegates to `search_collection` with `german_qdrant_manager`.

**Request body:** `SearchRequest`

**Response:** `SearchResponse` (HTTP 200)

---

### `POST /v1/search/eu`

Search the EU funding collection and return ranked matches. Rate-limited to 30 req/min per IP. Delegates to `search_collection` with `eu_qdrant_manager`.

**Request body:** `SearchRequest`

**Response:** `SearchResponse` (HTTP 200)

---

### `GET /v1/vocab/german`

Return the current German taxonomy contract artifact loaded from `taxonomy_german.json`. Returns a blank skeleton instead of an error when the file is missing or malformed. Rate-limited to 120 req/min per IP.

**Response:** `dict` with `domain`, `generated_at_utc`, `version`, `hash`, and `columns` keys.
