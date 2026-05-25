# `fastapi.utils.fastapi_utils`

Implements shared embedding-pipeline logic for loading processed data, generating embeddings, and syncing records to Qdrant.

## Module Constants

- `OLLAMA_URL`: base URL of the Ollama embedding service (default `"http://ollama:11434"`).
- `EMBED_MODEL`: Ollama model name for embedding (default `"bge-m3"`).
- `TOKENIZER`: HuggingFace tokenizer identifier (default `"BAAI/bge-m3"`).
- `OLLAMA_EMBED_TIMEOUT_SECONDS`: HTTP timeout for embedding requests (default `120`).
- `ADAPTIVE_CHUNK_THRESHOLD`: token count below which a document is returned as a single chunk instead of being windowed (default `600`).
- `PAYLOAD_EXCLUDE_FIELDS`: set of metadata keys excluded from Qdrant payloads to reduce storage (`{"description"}`).

## Top-Level Helpers

### `chunked(iterable, size)`

Yields fixed-size chunks from an iterable using `itertools.islice`.

### `load_funding_data(file_path, retries=10, delay=1)`

Reads a Parquet file with retry and exponential backoff (doubling up to 30 s) when the file is temporarily unavailable.

## Class `EmbeddingService`

Responsible for text chunking and embedding retrieval through Ollama.

### Constructor

- `ollama_url` (str, default=`OLLAMA_URL`): base URL of the Ollama service.
- `model` (str, default=`EMBED_MODEL`): embedding model name.
- `max_tokens` (int, default=`512`): maximum tokens per chunk.
- `overlap_tokens` (int, default=`62`): overlap between adjacent chunks.
- `tokenizer` (str, default=`TOKENIZER`): HuggingFace tokenizer loaded via `AutoTokenizer.from_pretrained`.

### `chunk_text(text)`

Splits a long text into overlapping token-based chunks suitable for embedding. Short documents (≤ `ADAPTIVE_CHUNK_THRESHOLD` tokens) are returned as a single chunk to avoid semantically impoverished tail fragments. Non-final chunks are trimmed to the last sentence boundary via `_snap_to_sentence`.

### `_snap_to_sentence(text)`

Trims text to the last sentence boundary in its trailing quarter. Searches the final 25% of the text for sentence-ending markers (`. `, `? `, `! ` and their newline variants) and truncates at the last one found. Returns the text unchanged if no boundary exists in the search region.

### `fetch_embedding(client, text)`

Calls the Ollama embeddings endpoint and returns a single embedding vector, or `None` on HTTP failure.

## Class `Pipeline`

Orchestrates Qdrant synchronization for processed funding data.

### Constructor

- `qdrant` (`QdrantManager`): Qdrant collection manager for insert/delete/scroll.
- `embed_service` (`EmbeddingService`): service that chunks text and fetches embeddings.
- `file_path` (str): path to the UUID Parquet file produced by `CommonDataPipeline`.

### `manage_embeddings()`

High-level workflow for embedding maintenance:

1. Load and normalize current funding data.
2. Fetch existing project IDs from Qdrant.
3. Delete removed/stale projects from the vector store.
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

Chunks one project description via `EmbeddingService.chunk_text`, prepends a contextual header (title + funding area) to each chunk, generates embeddings for all chunks via Ollama, and upserts the resulting points into Qdrant.

Uses indexed embeddings (`(i, emb)` tuples) to track which chunk indices succeeded, ensuring chunk IDs, sparse vectors, and metadata stay aligned even when individual embedding requests fail. The `description` field is excluded from payloads via `PAYLOAD_EXCLUDE_FIELDS` to reduce storage. Logs a warning and skips the project if no embeddings are generated.

#### `_fetch_existing_project_ids()`

Scrolls through the entire Qdrant collection (256 points per page) reading the `project_uuid` payload field. For legacy points that lack this field, the point ID itself is used as a fallback. Returns deduplicated project UUIDs as a list.
