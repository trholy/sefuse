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
| `PAYLOAD_EXCLUDE_FIELDS` | `set[str]` | `{"description", "legal_basis"}` | Metadata keys excluded from Qdrant payloads to reduce storage. |
| `PAYLOAD_DISPLAY_FIELDS` | `tuple[str, ...]` | see `utils/config.py` | The 18 payload keys the search API returns; the input to `compute_payload_hash`. |
| `PAYLOAD_LIST_FIELDS` | `frozenset[str]` | see `utils/config.py` | Which of those normalise an absent value to `[]` rather than `""`. |

---

## Top-Level Functions

### `compute_content_hash(metadata: dict, description: str) -> str`

Fingerprint the text that actually gets embedded: the contextual header plus the chunked body. Moves when the source text changes **and** when we change what the header is made of — a new entry in `CONTEXT_HEADER_FIELDS`, a vocabulary change, a parser mapping. That last part is what a marker taken from upstream (such as a `last_updated` column) cannot see.

Deliberately does **not** cover the embedding recipe (model name, chunk size, overlap, `ADAPTIVE_CHUNK_THRESHOLD`). Changing one of those invalidates every vector in the collection and warrants a deliberate full rebuild, not an implicit one.

**Returns:** `str` — hex SHA-256 digest.

---

### `compute_payload_hash(metadata: dict) -> str`

Fingerprint the fields the search API returns, per `PAYLOAD_DISPLAY_FIELDS` — not the whole payload. Keys such as `funding_body`, `license_info` and `more_info` are never returned, so hashing them would trigger refreshes nobody can observe.

Absent keys normalise exactly as `_aggregate_results` normalises them: missing scalar to `""`, missing list to `[]`. This is what makes the two collections comparable — EU carries no `status_note`, `deadlines` or `keywords_extracted` and only one `*_keys` field, while German carries no `date_1`/`date_2`. Without it, adding a column to one pipeline would silently invalidate the other's hashes.

**Returns:** `str` — hex SHA-256 digest.

---

### `build_project_payload(metadata: dict, project_id: str, description: str) -> dict`

The project-level Qdrant payload: the row minus `PAYLOAD_EXCLUDE_FIELDS`, plus `project_uuid` and both hashes. Shared by the insert path and the payload-refresh path so the two cannot write different payloads for the same row.

`chunk_index` is deliberately absent — it is the one payload key that differs between a project's chunks, so the caller adds it. Leaving it out is what lets a payload refresh use `set_payload`, which merges and therefore preserves each chunk's own index.

**Returns:** `dict` — payload without `chunk_index`.

---

### `_canonical_json(value: Any) -> str`

Serialise a value so equal content always produces equal bytes. Same convention as `TaxonomyContractBuilder.build_taxonomy_artifact`: `ensure_ascii=False, sort_keys=True, separators=(",", ":")`. `default=str` covers the EU rows, whose `date_1`/`date_2` are `datetime` objects rather than strings.

Both hashes are computed **from the parquet row**, never read back from Qdrant, so the same code serialises them every run.

---

### `build_context_header(metadata: dict, collection_type: str | None = None) -> str`

Build the contextual header prepended to every chunk of a project before it is embedded.

This is what makes fields other than `description` part of the embedding. `description` is the chunked body; everything else contributes through this header, declared once in `CONTEXT_HEADER_FIELDS`:

| Metadata key | Label |
|---|---|
| `title` | Title |
| `funding_type` | Funding type |
| `funding_area` | Funding area |
| `eligible_applicants` | Eligible applicants |
| `keywords_extracted` | Keywords |
| `project_short_description` | Summary |

The header is repeated on each chunk so a chunk taken from the middle of a long programme still carries what it is about. Keep it short for that reason: at roughly 115 tokens it already costs a fifth of the 512-token window, and every field added is paid for on every chunk of every project.

Lists are joined with `, `. Values equal to `PLACEHOLDER_VALUE` (`"N/A"`) are dropped, including single elements inside a list — `DataCleaner` writes that literal for every field the source does not state, and embedding it would put the same meaningless token into thousands of documents. A field that renders to nothing contributes no line; a project that states none of them gets an empty header.

`collection_type` selects the per-collection list caps in `HEADER_LIST_CAPS`. Only one entry exists: the EU collection caps `funding_area` at 20 elements. EU calls are tagged from a far broader vocabulary than German programmes — 6 areas at the median and 19 at p90, but the worst carries 213, a 1,591-token header on top of each 512-token window, so roughly 78% of that chunk's tokens were a taxonomy dump. The cap sits at p90, leaving ~90% of calls untouched and cutting the worst line from 1,546 to 211 tokens. It is applied after the placeholder filter, so a dropped `"N/A"` never consumes a slot. German is uncapped: its taxonomy is curated and short by construction.

**Capped rather than dropped — a design choice, not a measured retrieval win.** Dropping `funding_area` from the EU header entirely was tried first and measured against the collection's canary noise floor: "hydrogen electrolysis for industrial decarbonisation" scored 0.4907 dropped and 0.4881 capped, against a floor of 0.5151/0.5170. That is no material difference, so do not cite a retrieval measurement in favour of the cap. The cap is preferred because at the median of 6 areas the field is plausibly real topical signal, and capping bounds the token cost without discarding the median case.

Both of those EU numbers sit below the floor, which is a property of the corpus rather than of the header: the EU collection holds only the ~212 currently OPEN/FORTHCOMING calls, none of them specifically about hydrogen electrolysis. A query the corpus does cover — "circular economy in cities" — reaches 0.6916 and clears the floor. `relative_score` cannot show this either way, since the top hit always reads 1.0.

The cap governs the embedded text only: `funding_area` is untouched in the payload, still returned by the API, still filterable through `funding_area_keys`.

`None` caps nothing, which is the German field set — so existing no-argument callers are unaffected.

**Parameters:**

- `metadata` (`dict`): The project's row, as written to the Qdrant payload.

**Returns:** `str` — header text ending in a blank line, or `""`.

---

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

### `Pipeline(qdrant: QdrantManager, embed_service: EmbeddingService, file_path: str, http_client: httpx.AsyncClient | None = None, collection_type: str | None = None)`

Store references to the Qdrant manager, embedding service, and data file path.

**Parameters:**

- `qdrant` (`QdrantManager`): Qdrant collection manager for insert/delete/scroll operations.
- `embed_service` (`EmbeddingService`): Service that chunks text and fetches embeddings.
- `file_path` (`str`): Path to the UUID Parquet file produced by `CommonDataPipeline`.
- `http_client` (`httpx.AsyncClient | None`): Shared client reused for embedding requests.
- `collection_type` (`str | None`): `"german"` or `"eu"`. Keys the first-seen record used by saved-search alerts; `None` disables first-seen stamping.

---

### `manage_embeddings() -> None`

Run the full incremental embedding pipeline. Every project falls into one of four buckets:

| Bucket | Condition | Action |
|---|---|---|
| delete | indexed, no longer active | `delete_projects` |
| insert | active, not indexed | embed + insert |
| re-embed | indexed, `content_hash` differs or absent | `delete_projects`, **then** embed + insert |
| payload refresh | indexed, same `content_hash`, `payload_hash` differs | `set_project_payload` — no embedding call |

A project whose stored hashes are missing lands in the re-embed bucket, which is what makes the first run after this feature shipped a full re-index of both collections.

!!! warning "Re-embedding deletes first"
    Chunk point IDs are `uuid5(project_uuid, "chunk_{i}")`, so a bare re-upsert of a project that now produces *fewer* chunks would leave the surplus behind. Those orphans still carry the `project_uuid`, so they would be returned by search and folded into the project's aggregated score. Bucket 3 therefore issues one batched `delete_projects` before inserting.

Before the buckets are acted on, `_record_first_seen` stamps every active project that has no first-seen row (see below).

**Returns:** `None`

---

### `_record_first_seen(df: pl.DataFrame, indexed_ids: set[str]) -> list[str]`

Stamp every active programme that has no row in `programme_first_seen` yet, so saved-search alerts can tell a genuinely new programme from one that merely moved into a search's top results.

- Not yet in Qdrant → a genuine new arrival, stamped with the current time.
- Already in Qdrant but unstamped → predates tracking, stamped with the epoch (`1970-01-01`) so it can never count as new. This is what stops the first run after rollout replaying the whole index as alerts.
- Existing rows are never overwritten (`ON CONFLICT DO NOTHING`), so a programme that is deleted and later re-inserted keeps its original time.

- **Re-key guard:** if the collection already has rows and more than `max(FIRST_SEEN_BURST_MIN, FIRST_SEEN_BURST_RATIO * active)` programmes would be stamped as new, they are stamped with the epoch instead and an error is logged. Such a burst is upstream ids changing, not new programmes.

Database errors are logged and swallowed, so a Postgres outage never blocks embedding. The failure mode is one-sided: a programme that fails to be stamped can miss an alert but never trigger a false one. Does nothing when `collection_type` is `None`.

**Returns:** the ids stamped as genuinely new in this run.

---

### `_mark_duplicates(new_ids: list[str]) -> None`

Called after embedding for the programmes stamped new in this run. Fetches each one's chunk-0 vector and its nearest programme outside this run's new ones; at cosine >= `DUPLICATE_COSINE` (default 0.97) it records `programme_first_seen.duplicate_of`, so the programme does not alert as new. Failures are logged and skipped.

The Qdrant lookups are per programme, but the marks are collected and written by a single `first_seen.mark_duplicates` call after the loop — one connection per duplicate meant hundreds of them on the first run after a re-index.

---

### `_plan_index_updates(df: pl.DataFrame, indexed: dict[str, dict]) -> tuple[pl.DataFrame, list[str], list[tuple[str, dict]]]`

Sort the active rows into the embed, re-embed and payload-refresh buckets. Pure and synchronous, so classification is testable without Qdrant or Ollama.

**Parameters:**

- `df` (`pl.DataFrame`): Full funding DataFrame, including deleted rows.
- `indexed` (`dict[str, dict]`): Per-project stored hashes from `_fetch_indexed_state`, with deleted projects already removed.

**Returns:** `(rows_to_embed, stale_ids, payload_updates)` — the rows needing an embedding pass, the subset of those already indexed (which must be deleted first), and `(project_uuid, payload)` pairs that can be refreshed in place.

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

### `_fetch_indexed_state() -> dict[str, dict]`

Scroll the Qdrant collection and return each indexed project's stored change markers.

Reads `project_uuid`, `content_hash` and `payload_hash` from each point (256 points per page, selective payload projection). Uses the raw point ID as a fallback for legacy points lacking `project_uuid`. Every chunk of a project carries the same hashes, so the first chunk seen wins. A project indexed before this feature existed yields `None` for both hashes, which `_plan_index_updates` treats as changed. Propagates Qdrant scroll errors so the embedding run aborts rather than silently treating the collection as empty.

**Returns:** `dict[str, dict]` — `{project_uuid: {"content_hash": …, "payload_hash": …}}`.

**Raises:** `Exception` — any Qdrant scroll error propagates to the caller.
