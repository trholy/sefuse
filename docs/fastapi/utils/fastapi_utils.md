# `fastapi.utils.fastapi_utils`

Implements shared embedding-pipeline logic for loading processed data, generating embeddings, and syncing records to Qdrant.

## Top-Level Helpers

### `chunked(iterable, size)`

Yields fixed-size chunks from an iterable using `itertools.islice`.

### `load_funding_data(file_path, retries=10, delay=1)`

Reads a parquet file with retry and exponential backoff behavior when the file is temporarily unavailable.

## Class `EmbeddingService`

Responsible for text chunking and embedding retrieval through Ollama.

### Constructor

- `ollama_url`: base URL of the Ollama service.
- `model`: embedding model name.
- `max_tokens`: maximum tokens per chunk.
- `overlap_tokens`: overlap between adjacent chunks.
- `tokenizer`: tokenizer model loaded via Hugging Face Transformers.

### `chunk_text(text)`

Splits a long text into overlapping token-based chunks suitable for embedding.

### `fetch_embedding(client, text)`

Calls the Ollama embeddings endpoint and returns a single embedding vector, or `None` on HTTP failure.

## Class `Pipeline`

Orchestrates Qdrant synchronization for processed funding data.

### Constructor

- `qdrant`: `QdrantManager` instance.
- `embed_service`: `EmbeddingService` instance.
- `file_path`: parquet file containing UUID-enriched records.

### `manage_embeddings()`

High-level workflow for embedding maintenance:

1. Load and normalize current funding data.
2. Fetch existing IDs from Qdrant.
3. Delete removed projects from the vector store.
4. Determine active projects that are not yet indexed.
5. Generate embeddings and insert them into Qdrant.

### Internal Methods

#### `_load_and_normalize_data()`

Loads the Parquet file via `load_funding_data` and casts the `uuid` column to UTF-8 strings.

#### `_delete_removed_projects(df, existing_ids)`

Computes the set difference between Qdrant-stored IDs and currently active project IDs, then deletes stale entries from the collection.

#### `_get_new_active_rows(df, existing_ids)`

Filters the DataFrame to active (not deleted) rows whose UUIDs are not yet present in the Qdrant collection.

#### `_embed_and_insert_rows(new_rows)`

Iterates through new rows, calling `_process_single_project` for each one within a shared `httpx.AsyncClient` session.

#### `_process_single_project(client, description, metadata, project_id)`

Chunks one project description via `EmbeddingService.chunk_text`, generates embeddings for all chunks, and upserts the resulting points into Qdrant. Logs a warning and skips the project if no embeddings are generated.

#### `_generate_embeddings(client, chunks)`

Fetches dense embedding vectors for each text chunk from Ollama via `EmbeddingService.fetch_embedding`. Chunks that fail to embed are silently skipped.

#### `_insert_project_embeddings(embeddings, metadata, project_id)`

Writes one or more embedding vectors for a single project to Qdrant, replicating the metadata payload across all chunk points.

#### `_fetch_existing_ids()`

Scrolls through the entire Qdrant collection (256 points per page, no payload or vector data) and returns all stored point IDs. Returns an empty list if the scroll fails.
