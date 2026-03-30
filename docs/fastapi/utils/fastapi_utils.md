# `fastapi.utils.fastapi_utils`

Implements shared embedding-pipeline logic for loading processed data, generating embeddings, and syncing records to Qdrant.

## Top-Level Helpers

### `download_job()`

Triggers the German data pipeline and logs success or failure.

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

- `_load_and_normalize_data()`: reads parquet data and casts UUIDs to strings.
- `_delete_removed_projects(df, existing_ids)`: removes deleted projects already stored in Qdrant.
- `_get_new_active_rows(df, existing_ids)`: returns active records missing from the vector store.
- `_embed_and_insert_rows(new_rows)`: loops through new records and processes each one.
- `_process_single_project(client, description, metadata, project_id)`: chunks one description, generates embeddings, and stores them.
- `_generate_embeddings(client, chunks)`: embeds all chunks and keeps successful results.
- `_insert_project_embeddings(embeddings, metadata, project_id)`: writes one or more vectors for a project to Qdrant.
- `_fetch_existing_ids()`: scrolls Qdrant to collect all stored point IDs.
