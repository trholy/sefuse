# `fastapi.utils.qdrant_utils`

Manages a Qdrant collection configured for hybrid (dense + sparse) vector search with Convex Combination (CC) fusion.

## Module Constants

- `VECTOR_DB_HOST`: Qdrant host (default `"qdrant"`).
- `QDRANT_PORT`: Qdrant port (default `6333`).
- `DENSE_VECTOR_NAME`: named vector key for dense embeddings (`"dense"`).
- `SPARSE_VECTOR_NAME`: named vector key for sparse BM25-style vectors (`"sparse"`).
- `PREFETCH_LIMIT_MULTIPLIER`: multiplier applied to `limit` when computing prefetch sizes for each fusion branch.
- `STOPWORDS`: `frozenset` of German and English stopwords sourced from the `stop-words` library, filtered before tokenization.
- `BM25_K1`: saturation parameter for BM25 term-frequency weighting (default `1.2`).
- `PAYLOAD_INDEX_FIELDS`: tuple of payload field names that receive keyword indexes for fast filtering (`project_uuid`, `funding_type_keys`, `funding_area_keys`, `funding_location_keys`, `eligible_applicants_keys`).

## Module-Level Functions

### `_bm25_saturate(tf, k1=BM25_K1)`

Applies BM25 term-frequency saturation: `tf * (k1 + 1) / (tf + k1)`. Sublinear weighting prevents high-frequency terms from dominating the sparse vector.

### `_split_compound(word)`

Attempts to split a German compound word into two parts at a fugen element (`s`, `es`, `n`, `en`, `er`, `e`, `ns`, `ens`). Selects the most balanced split (closest to 50/50 length ratio). Returns a two-element list on success, or an empty list if the word is too short (`< 10` chars) or no valid split exists.

## Class `QdrantManager`

### Constructor

- `host` (str, default=`VECTOR_DB_HOST`): Qdrant server hostname.
- `port` (int, default=`QDRANT_PORT`): Qdrant service port.
- `collection_name` (str, default=`"fundings"`): target collection name (e.g. `"fundings_german"`, `"fundings_eu"`).

On construction the client connects to Qdrant with retries and ensures the collection exists with the
hybrid vector schema (dense cosine 1024-dim + sparse IDF). Existing collections missing one of the
named vector configs are migrated automatically. Payload keyword indexes are created for frequently filtered fields.

### `_init_qdrant(max_retries=10, wait=3)`

Connects to Qdrant with linear back-off retries and ensures the collection has the hybrid-search schema. If the collection does not exist it is created; if it exists but lacks named dense or sparse vector configs it is migrated (recreated or updated). Calls `_ensure_payload_indexes` before returning. Raises `RuntimeError` after all retries are exhausted.

Schema:

- `dense`: 1024-dimensional cosine distance.
- `sparse`: IDF-modified sparse vectors for keyword search.

### `_ensure_payload_indexes(client)`

Creates keyword payload indexes for fields listed in `PAYLOAD_INDEX_FIELDS`. Silently skips fields whose indexes already exist. Indexes accelerate `FilterSelector` and `FieldCondition` queries used by `delete_projects` and server-side taxonomy filtering.

### `_tokenize(text)`

Tokenizes text for sparse vector construction. Pipeline: lowercase → regex word extraction (`\b\w+\b`) → stopword removal → German Snowball stemming → compound splitting (with stemming of parts). Compound parts are appended alongside the original stem so that both the full compound and its constituents contribute to the sparse vector.

### `_token_to_index(token)`

Maps a token to a stable 32-bit integer index via the first 8 hex digits of its MD5 hash.

### `_build_sparse_vector(text)`

Builds a `SparseVector` from BM25-saturated term frequencies. Tokenises the text via `_tokenize` (stemming + compound splitting), counts occurrences, applies `_bm25_saturate` to each count, maps each token to a stable integer index via `_token_to_index`, and returns a sparse vector suitable for BM25-style retrieval. Returns an empty vector when the text yields no tokens.

### `_build_point_vector(embedding, chunk_text)`

Combines a pre-computed dense embedding and a chunk-text-derived sparse vector (built via `_build_sparse_vector`) into a named-vector dict with keys `dense` and `sparse`.

### `insert_projects(embeddings, metadata_list, ids, chunk_texts)`

Builds `PointStruct` entries with both dense and sparse vectors and upserts them in a single batch. Sparse vectors are derived from the enriched chunk texts (which include contextual headers but not the embedding prefix).

### `delete_projects(project_uuids)`

Deletes points by `project_uuid` payload field via `FilterSelector` (for chunked points), and also by direct point-ID deletion (for legacy pre-migration points). No-op for an empty list.

### `search(query_vector, query_text="", limit=20, semantic_weight=0.7)`

Runs hybrid search using Convex Combination (CC) fusion and returns scored points.

`semantic_weight` controls the search mode:

- `1.0`: pure dense (cosine) search.
- `0.0`: pure sparse (BM25 keyword) search.
- `0.0 < w < 1.0`: CC fusion — dense and sparse results are fetched independently with
  prefetch limits proportional to `semantic_weight` (floor of `limit` per branch), then fused via `_fuse_convex_combination`.

### `_fuse_convex_combination(dense_points, sparse_points, semantic_weight, limit)`

Fuses dense and sparse results via score-aware Convex Combination. Each source's scores are min-max normalized independently, then combined as `score = w * d_norm + (1-w) * s_norm`. Points appearing in only one source receive `0.0` for the missing component. Single-point result sets normalize to `1.0`. Returns `SimpleNamespace` objects with `.id`, `.score`, and `.payload`, sorted by descending fused score, truncated to `limit`.
