# `fastapi.main`

Defines the FastAPI application, startup jobs, scheduled refresh workflows, and funding search endpoints.

## Main Responsibilities

- Configures environment-backed runtime settings for embeddings, collections, and file paths.
- Starts German and EU data-processing jobs on application startup.
- Starts embedding refresh pipelines on startup and on a cron schedule.
- Exposes REST endpoints for German and EU funding search.
- Aggregates chunk-level Qdrant matches into project-level API responses.

## Key Functions

### `_normalize_list_field(value)`

Ensures a payload field is always returned as a list.

### `_aggregate_results(results)`

Combines chunk-level vector search results by project ID.

- Uses `id_url` when available, otherwise falls back to the vector point ID.
- Preserves project metadata from the first hit.
- Keeps the maximum match score across duplicates.

### `_embed_query(query, model)`

Calls the Ollama embeddings API and returns the query vector.

### `_search_collection(request, qdrant_manager)`

Reads the incoming request body, embeds the user query, performs hybrid search, and returns a `{"matches": ...}` response payload.

### `lifespan(app)`

FastAPI lifespan handler that:

1. Runs both data pipelines on startup.
2. Runs both embedding pipelines on startup.
3. Registers scheduled German and EU processing jobs with `AsyncIOScheduler`.
4. Starts the scheduler and shuts it down cleanly on application exit.

## Application State

- Creates one `EmbeddingService`.
- Creates separate `QdrantManager` instances for German and EU collections.
- Creates separate `Pipeline` instances for German and EU embedding maintenance.

## API Endpoints

### `POST /v1/search/german`

Searches the German funding collection.

### `POST /v1/search/eu`

Searches the EU funding collection.
