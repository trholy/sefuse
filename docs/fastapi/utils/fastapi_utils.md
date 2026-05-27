# `fastapi.utils.fastapi_utils`

Implements shared embedding-pipeline logic for loading processed data, generating embeddings via Ollama, and syncing records to Qdrant.

---

## Module Constants

| Constant | Type | Default | Description |
|---|---|---|---|
| `OLLAMA_URL` | `str` | `"http://ollama:11434"` | Base URL of the Ollama embedding service. |
| `EMBED_MODEL` | `str` | `"bge-m3"` | Ollama model name for embedding. |
| `TOKENIZER` | `str` | `"BAAI/bge-m3"` | HuggingFace tokenizer identifier used for chunk boundary calculation. |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `float` | `120.0` | HTTP timeout for embedding requests. |
| `ADAPTIVE_CHUNK_THRESHOLD` | `int` | `600` | Token count below which a document is embedded as a single chunk. |
| `EMBEDDING_CONCURRENCY` | `int` | `4` | Maximum number of projects embedded concurrently. Controls the `asyncio.Semaphore` in `_embed_and_insert_rows`. |
| `PAYLOAD_EXCLUDE_FIELDS` | `set[str]` | `{"description"}` | Metadata keys excluded from Qdrant payloads to reduce storage. |

---

## Top-Level Functions

### `load_funding_data(file_path: str, retries: int = 10, delay: int = 1) -> pl.DataFrame`

Read a Parquet file with exponential-backoff retries.

Useful when the data-processing container is still writing the file while FastAPI starts up.

**Parameters:**

- `file_path` (`str`): Path to the Parquet file.
- `retries` (`int`, default `10`): Maximum number of read attempts.
- `delay` (`int`, default `1`): Initial wait in seconds between attempts; doubles each retry up to a maximum of 30 seconds.

**Returns:** `pl.DataFrame` — loaded funding data.

**Raises:** `FileNotFoundError` — if the file is still absent after all retries (re-raised from the last attempt).

---

## Class `EmbeddingService`

Chunks long texts and fetches dense embeddings from the local Ollama service.

### `EmbeddingService(ollama_url: str = OLLAMA_URL, model: str = EMBED_MODEL, max_tokens: int = 512, overlap_tokens: int = 62, tokenizer: str = TOKENIZER)`

Initialise the embedding service and load the HuggingFace tokenizer via `AutoTokenizer.from_pretrained`.

**Parameters:**

- `ollama_url` (`str`, default `OLLAMA_URL`): Base URL of the Ollama API.
- `model` (`str`, default `EMBED_MODEL`): Ollama model name used for embedding.
- `max_tokens` (`int`, default `512`): Maximum tokens per chunk window.
- `overlap_tokens` (`int`, default `62`): Token overlap between adjacent chunks (~12% of window).
- `tokenizer` (`str`, default `TOKENIZER`): HuggingFace tokenizer identifier for token counting.

---

### `chunk_text(text: str) -> list[str]`

Split text into overlapping token-based chunks suitable for embedding.

Short documents (≤ `ADAPTIVE_CHUNK_THRESHOLD` tokens) are returned as a single chunk to avoid semantically impoverished tail fragments. Non-final chunks are trimmed to the last sentence boundary via `_snap_to_sentence`.

**Parameters:**

- `text` (`str`): Input text to split.

**Returns:** `list[str]` — decoded text chunks of at most `max_tokens` tokens with `overlap_tokens` overlap.

---

### `_snap_to_sentence(text: str, min_keep_chars: int) -> str`

Trim a decoded chunk to the last sentence boundary at or after `min_keep_chars`.

Searches the region beyond `min_keep_chars` for sentence-ending markers (`. `, `? `, `! ` and their newline variants) and truncates at the last one found. `min_keep_chars` is computed by the caller from the first 75% of the chunk's tokens.

**Parameters:**

- `text` (`str`): Decoded chunk text to trim.
- `min_keep_chars` (`int`): Minimum number of characters to preserve; derived from decoding the first 75% of the chunk's tokens.

**Returns:** `str` — text truncated at the last sentence boundary, or the original text if no boundary is found.

---

### `fetch_embeddings_batch(client: httpx.AsyncClient, texts: list[str]) -> list[list[float] | None]`

Request dense embedding vectors for a batch of texts in a single Ollama call.

Sends one `POST /api/embed` with `input: [...]`. Returns vectors in the same order as `texts`; pads with `None` when the response contains fewer embeddings than requested.

**Parameters:**

- `client` (`httpx.AsyncClient`): Shared async HTTP client.
- `texts` (`list[str]`): Texts to embed in one request.

**Returns:** `list[list[float] | None]` — embedding vectors, one per input text. `None` at an index means that embedding failed.

---

### `fetch_embedding(client: httpx.AsyncClient, text: str) -> list[float] | None`

Request a dense embedding vector for a single text. Thin wrapper around `fetch_embeddings_batch`.

**Parameters:**

- `client` (`httpx.AsyncClient`): Shared async HTTP client.
- `text` (`str`): Text to embed.

**Returns:** `list[float] | None` — embedding vector, or `None` if the request fails.

---

## Class `Pipeline`

Orchestrates incremental Qdrant synchronisation for processed funding data: reads new Parquet rows, generates embeddings, and upserts into the collection.

### `Pipeline(qdrant: QdrantManager, embed_service: EmbeddingService, file_path: str)`

Store references to the Qdrant manager, embedding service, and data file path.

**Parameters:**

- `qdrant` (`QdrantManager`): Qdrant collection manager for insert/delete/scroll operations.
- `embed_service` (`EmbeddingService`): Service that chunks text and fetches embeddings.
- `file_path` (`str`): Path to the UUID Parquet file produced by `CommonDataPipeline`.

---

### `manage_embeddings() -> None`

Run the full incremental embedding pipeline.

1. Load and normalise the Parquet file.
2. Fetch existing project IDs from Qdrant.
3. Delete stale projects no longer in the active data.
4. Identify rows not yet indexed.
5. Embed and upsert new rows.

**Returns:** `None`

---

### `_load_and_normalize_data() -> pl.DataFrame`

Load the Parquet file via `load_funding_data` and cast the `uuid` column to UTF-8 strings.

**Returns:** `pl.DataFrame` — with a string-typed `uuid` column.

---

### `_delete_removed_projects(df: pl.DataFrame, existing_ids: set[str]) -> list[str]`

Delete Qdrant points for projects no longer active in the Parquet file.

Computes the set difference between `existing_ids` and the UUIDs of active (non-deleted) rows in `df`, then removes the stale entries.

**Parameters:**

- `df` (`pl.DataFrame`): Full funding DataFrame including deleted rows.
- `existing_ids` (`set[str]`): Project UUIDs currently indexed in Qdrant.

**Returns:** `list[str]` — UUIDs deleted from Qdrant (empty if nothing to delete).

---

### `_get_new_active_rows(df: pl.DataFrame, existing_ids: set[str]) -> pl.DataFrame`

Filter the DataFrame to active rows whose UUIDs are not yet in Qdrant.

**Parameters:**

- `df` (`pl.DataFrame`): Full funding DataFrame (includes deleted rows).
- `existing_ids` (`set[str]`): UUIDs already present in the Qdrant collection.

**Returns:** `pl.DataFrame` — subset of active, not-yet-indexed rows.

---

### `_embed_and_insert_rows(new_rows: pl.DataFrame) -> None`

Embed and upsert all rows concurrently with bounded parallelism.

Builds one async task per project and runs them via `asyncio.gather`, gated by `asyncio.Semaphore(EMBEDDING_CONCURRENCY)`. Opens a dedicated `httpx.AsyncClient` (connection limits + `OLLAMA_EMBED_TIMEOUT_SECONDS`) for the duration of the batch.

**Parameters:**

- `new_rows` (`pl.DataFrame`): Active, not-yet-indexed rows to process.

**Returns:** `None`

---

### `_process_single_project(client: httpx.AsyncClient, description: str, metadata: dict, project_id: str) -> None`

Chunk, embed, and upsert one project into Qdrant.

Prepends a contextual header (`Title: ...\nFunding area: ...\n\n`) to each chunk, calls `fetch_embeddings_batch` once for all enriched chunks, then upserts only chunks whose embeddings succeeded. Each chunk receives a deterministic UUID5 point ID derived from `uuid5(project_uuid, "chunk_{i}")`. Logs a warning and skips the project if no embeddings are generated.

**Parameters:**

- `client` (`httpx.AsyncClient`): Shared async HTTP client for Ollama requests.
- `description` (`str`): Full project description text to chunk and embed.
- `metadata` (`dict`): Payload dict stored alongside each point in Qdrant (minus `PAYLOAD_EXCLUDE_FIELDS`).
- `project_id` (`str`): Project UUID used as the namespace for chunk point IDs.

**Returns:** `None`

---

### `_fetch_existing_project_ids() -> list[str]`

Scroll the Qdrant collection and return unique project UUIDs.

Reads the `project_uuid` payload field from each point (256 points per page). Uses the raw point ID as a fallback for legacy points that lack the field. Propagates Qdrant scroll errors to the caller so the embedding run aborts rather than silently treating the collection as empty.

**Returns:** `list[str]` — deduplicated project UUIDs currently indexed.

**Raises:** `Exception` — any Qdrant scroll error propagates to the caller.
