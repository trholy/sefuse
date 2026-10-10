# `fastapi.utils.qdrant_utils`

Manages a Qdrant collection configured for hybrid (dense + sparse) vector search with Convex Combination (CC) fusion.

---

## Module Constants

| Constant | Type | Default | Description |
|---|---|---|---|
| `VECTOR_DB_HOST` | `str` | `"qdrant"` | Qdrant server hostname. |
| `QDRANT_PORT` | `int` | `6333` | Qdrant HTTP/gRPC port. |
| `DENSE_VECTOR_NAME` | `str` | `"dense"` | Named vector key for dense embeddings. |
| `SPARSE_VECTOR_NAME` | `str` | `"sparse"` | Named vector key for sparse BM25-style vectors. |
| `PREFETCH_LIMIT_MULTIPLIER` | `int` | `5` | Multiplier applied to `limit` when computing per-branch prefetch sizes for CC fusion. |
| `GERMAN` / `ENGLISH` | `str` | `"german"` / `"english"` | The two supported sparse-analysis languages. |
| `_STOPWORDS` | `dict[str, frozenset[str]]` | — | Stopwords per language from the `stop-words` library, filtered before tokenization. `german` is the German + English union; `english` is English only. |
| `_STEMMERS` | `dict[str, Stemmer]` | — | Snowball stemmer per language. |
| `BM25_K1` | `float` | `1.2` | BM25 term-frequency saturation parameter. |
| `PAYLOAD_INDEX_FIELDS` | `tuple[str, ...]` | `("project_uuid", "funding_type_keys", "funding_area_keys", "funding_location_keys", "eligible_applicants_keys")` | Payload fields that receive keyword indexes for fast filtering. |

---

## Module-Level Functions

### `_bm25_saturate(tf: float, k1: float = BM25_K1) -> float`

Apply BM25 term-frequency saturation to a raw count.

Sublinear weighting prevents high-frequency terms from dominating the sparse vector: `tf * (k1 + 1) / (tf + k1)`.

**Parameters:**

- `tf` (`float`): Raw term frequency.
- `k1` (`float`, default `BM25_K1`): Saturation parameter. Lower values saturate faster; `1.2` is the standard BM25 default.

**Returns:** `float` — saturated term weight in the range `(0, k1 + 1)`.

---

### `_split_compound(word: str) -> list[str]`

Split a German compound word into two parts at a fugen element.

Tries every candidate split position and fugen element (`s`, `es`, `n`, `en`, `er`, `e`, `ns`, `ens`). Selects the most balanced split (closest to 50/50 length ratio). Words shorter than `_MIN_COMPOUND_LENGTH` (10 chars) or those with no valid split return `[]`.

Decorated with `@lru_cache(maxsize=10_000)` — repeated compound strings (funding area and location values) are split only once per process lifetime.

Called for German text only. English compounds are space-separated, so the German fugen elements produce nothing but noise on English input (`organisation` → `organi` + `ation`).

**Parameters:**

- `word` (`str`): Lowercased token to attempt splitting.

**Returns:** `list[str]` — two-element list `[left, right]` on success, or `[]` if no valid split is found.

---

## Class `QdrantManager`

Manages a Qdrant collection with a hybrid-search schema (dense cosine + IDF sparse). On construction the collection is created or migrated as needed.

### `QdrantManager(host: str = VECTOR_DB_HOST, port: int = QDRANT_PORT, collection_name: str = "fundings", language: str = GERMAN)`

Connect to Qdrant and ensure the named collection is hybrid-search ready.

**Parameters:**

- `host` (`str`, default `VECTOR_DB_HOST`): Qdrant server hostname.
- `port` (`int`, default `QDRANT_PORT`): Qdrant HTTP/gRPC port.
- `collection_name` (`str`, default `"fundings"`): Name of the collection to manage (e.g. `"fundings_german"`, `"fundings_eu"`).
- `language` (`str`, default `GERMAN`): Language of the indexed text, selecting the stopword list and stemmer used for sparse vectors. Raises `ValueError` for an unsupported value.

`language` is also a **class attribute** defaulting to `GERMAN`, so instances built via `__new__` (as several tests do) still resolve `self.language`.

---

### `_vectors_include_dense(vectors_config: Any) -> bool`

Check whether the collection already has a named dense vector config.

**Parameters:**

- `vectors_config` (`Any`): `config.params.vectors` from `client.get_collection()`.

**Returns:** `bool` — `True` if a `"dense"` key exists in the mapping.

---

### `_sparse_vectors_include_sparse(sparse_vectors_config: Any) -> bool`

Check whether the collection already has a named sparse vector config.

**Parameters:**

- `sparse_vectors_config` (`Any`): `config.params.sparse_vectors` from `client.get_collection()`.

**Returns:** `bool` — `True` if a `"sparse"` key exists in the mapping.

---

### `_hybrid_collection_config() -> dict[str, Any]`

Return the canonical vector and sparse-vector config dict for creating or recreating a hybrid collection.

**Returns:** `dict[str, Any]` — contains `vectors_config` (1024-dim cosine) and `sparse_vectors_config` (IDF-modified sparse).

---

### `_init_qdrant(max_retries: int = 10, wait: int = 3) -> QdrantClient`

Connect to Qdrant and ensure the collection has the hybrid-search schema.

If the collection does not exist it is created. If it exists but lacks named dense vectors it is recreated. If it exists with dense but lacks sparse vectors, the sparse config is added via `update_collection`. Calls `_ensure_payload_indexes` before returning.

**Parameters:**

- `max_retries` (`int`, default `10`): Connection attempts before raising.
- `wait` (`int`, default `3`): Seconds between retries.

**Returns:** `QdrantClient` — connected client instance.

**Raises:** `RuntimeError` — if Qdrant is unreachable after all retries.

---

### `_ensure_payload_indexes(client: QdrantClient) -> None`

Create keyword payload indexes for fields listed in `PAYLOAD_INDEX_FIELDS`.

Silently skips fields whose indexes already exist. Indexes accelerate `FilterSelector` and `FieldCondition` queries used by `delete_projects` and server-side taxonomy filtering.

**Parameters:**

- `client` (`QdrantClient`): Connected Qdrant client.

**Returns:** `None`

---

### `_tokenize(text: str, language: str = GERMAN) -> list[str]`

Tokenize, stem, and compound-expand text for sparse vector construction.

Pipeline: lowercase → regex word extraction (`\b\w+\b`) → stopword removal → Snowball stemming in `language` → compound splitting (with stemming of split parts). Compound parts are appended alongside the original stem.

Compound splitting runs for `GERMAN` only; see `_split_compound`.

**Parameters:**

- `text` (`str`): Input text (typically an enriched chunk with contextual header).
- `language` (`str`, default `GERMAN`): Language whose stopword list and stemmer to use.

**Returns:** `list[str]` — stemmed and expanded tokens (may contain duplicates for term-frequency counting).

---

### `_token_to_index(token: str) -> int`

Map a token string to a stable 32-bit integer index via MD5 hashing.

**Parameters:**

- `token` (`str`): Stemmed token.

**Returns:** `int` — deterministic index derived from the first 8 hex digits of the MD5 digest.

---

### `_build_sparse_vector_from_tokens(token_counts: Counter) -> SparseVector`

Build a BM25-saturated sparse vector from a pre-computed token `Counter`.

Applies `_bm25_saturate` to each term frequency, maps tokens to 32-bit indices via `_token_to_index`, resolves hash collisions by summing BM25 values, and returns a sorted sparse vector.

**Parameters:**

- `token_counts` (`Counter`): Token frequency map from `_tokenize`.

**Returns:** `SparseVector` — sparse vector with unique sorted indices and BM25-saturated values, or an empty vector when the counter is empty.

---

### `_build_sparse_vector(text: str, language: str = GERMAN) -> SparseVector`

Build a BM25-saturated sparse vector from raw text. Thin wrapper around `_build_sparse_vector_from_tokens`.

**Parameters:**

- `text` (`str`): Input text to vectorize.
- `language` (`str`, default `GERMAN`): Language whose stopword list and stemmer to use.

**Returns:** `SparseVector` — sparse vector, or empty when no tokens survive filtering.

---

### `_build_point_vector(self, embedding: list[float], chunk_text: str) -> dict[str, Any]`

Combine a pre-computed dense embedding and a chunk-text-derived sparse vector into a named-vector dict.

An **instance method** (not static) so the sparse vector is built in this collection's own `language`.

**Parameters:**

- `embedding` (`list[float]`): Pre-computed dense embedding vector.
- `chunk_text` (`str`): Enriched chunk text used for sparse vector construction (includes contextual header).

**Returns:** `dict[str, Any]` — named-vector dict with `"dense"` and `"sparse"` keys, ready for `PointStruct.vector`.

---

### `insert_projects(embeddings: list[list[float]], metadata_list: list[dict[str, Any]], ids: list[str], chunk_texts: list[str]) -> None`

Upsert project chunks into the Qdrant collection with both dense and sparse vectors.

**Parameters:**

- `embeddings` (`list[list[float]]`): Dense embedding vectors, one per chunk.
- `metadata_list` (`list[dict[str, Any]]`): Payload dicts for each chunk.
- `ids` (`list[str]`): Deterministic UUID5 point IDs.
- `chunk_texts` (`list[str]`): Enriched chunk texts used for sparse vector construction.

**Returns:** `None`

---

### `delete_projects(project_uuids: list[str]) -> None`

Delete all Qdrant points belonging to the given project UUIDs using a `FilterSelector` on the `project_uuid` payload field. No-op for an empty list.

**Parameters:**

- `project_uuids` (`list[str]`): Project UUIDs whose chunk-points should be removed.

**Returns:** `None`

---

### `set_project_payload(project_uuid: str, payload: dict[str, Any]) -> None`

Update the payload of every chunk of one project, leaving its vectors untouched.

Used for a project whose displayed fields changed but whose embedded text did not: re-embedding it would produce identical vectors at the cost of an Ollama round trip per chunk. Targets the project with the same `Filter`/`FieldCondition`/`MatchAny` shape as `delete_projects`.

!!! note "set_payload merges, it does not replace"
    That is what preserves each chunk's own `chunk_index`, which is why `build_project_payload` leaves that key out. The corollary is that a key *removed* from the source is not removed here; it clears on the project's next re-embed, or on a manual rebuild.

**Parameters:**

- `project_uuid` (`str`): Project whose chunks should be updated.
- `payload` (`dict[str, Any]`): Project-level payload, without `chunk_index`.

**Returns:** `None`

---

### `best_chunk_per_project(query_vector, *, project_uuids=None, exclude=None, limit=None, with_payload=True) -> list[ScoredPoint]`

Return each project's best-scoring dense chunk, best project first, via `query_points_groups(group_by="project_uuid", group_size=1)`. Every project takes exactly one slot, so no chunk budget has to be guessed. With `project_uuids` the search is exact (non-HNSW) and restricted to those projects, and `limit` defaults to their count; otherwise `limit` is required. `exclude` leaves projects out. Used by the alert job (candidate scores, rank reference, canary noise floor) and the near-duplicate check.

---

### `project_vector(project_uuid: str) -> list[float] | None`

Fetch the dense vector of a project's first chunk by its id (`uuid5(project_uuid, "chunk_0")`), or `None` when it is missing. Used by `Pipeline._mark_duplicates`.

---

### `search(query_vector: list[float], query_text: str = "", limit: int = 20, semantic_weight: float = 0.7) -> list[Any]`

Run hybrid search using Convex Combination (CC) fusion and return scored points.

`semantic_weight` controls the search mode:

- `1.0`: pure dense (cosine) search.
- `0.0`: pure sparse (BM25 keyword) search.
- Between `0.0` and `1.0`: CC fusion — dense and sparse results fetched independently with prefetch limits scaled by `PREFETCH_LIMIT_MULTIPLIER * semantic_weight` (floor of `limit`), then fused via `_fuse_convex_combination`.

**Parameters:**

- `query_vector` (`list[float]`): Dense embedding of the search query.
- `query_text` (`str`, default `""`): Raw query text for sparse vector construction.
- `limit` (`int`, default `20`): Maximum number of results to return.
- `semantic_weight` (`float`, default `0.7`): Blend weight clamped to `[0, 1]`.

**Returns:** `list[Any]` — scored points (`ScoredPoint` or `SimpleNamespace` with `.id`, `.score`, `.payload`), sorted by descending fused score.

---

### `_fuse_convex_combination(dense_points: list, sparse_points: list, semantic_weight: float, limit: int) -> list`

Fuse dense and sparse results via score-aware Convex Combination.

Each source's scores are min-max normalized independently, then combined as `score = w * d_norm + (1-w) * s_norm`. Points appearing in only one source receive `0.0` for the missing component. Single-point result sets normalize to `1.0`.

**Parameters:**

- `dense_points` (`list`): Scored points from the dense (cosine) query.
- `sparse_points` (`list`): Scored points from the sparse (BM25) query.
- `semantic_weight` (`float`): Weight for the dense component.
- `limit` (`int`): Maximum number of fused results to return.

**Returns:** `list` — `SimpleNamespace` objects with `.id`, `.score`, and `.payload`, sorted by descending fused score, truncated to `limit`.
