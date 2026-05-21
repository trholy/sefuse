# `fastapi.utils.qdrant_utils`

Manages a Qdrant collection configured for hybrid (dense + sparse) vector search with RRF fusion.

## Module Constants

- `VECTOR_DB_HOST`: Qdrant host (default `"qdrant"`).
- `QDRANT_PORT`: Qdrant port (default `6333`).
- `DENSE_VECTOR_NAME`: named vector key for dense embeddings (`"dense"`).
- `SPARSE_VECTOR_NAME`: named vector key for sparse BM25-style vectors (`"sparse"`).
- `PREFETCH_LIMIT_MULTIPLIER`: multiplier applied to `limit` when computing RRF prefetch sizes.

## Class `QdrantManager`

### Constructor

- `host`: Qdrant server hostname.
- `port`: Qdrant service port.
- `collection_name`: target collection name (e.g. `"fundings_german"`, `"fundings_eu"`).

On construction the client connects to Qdrant with retries and ensures the collection exists with the
hybrid vector schema (dense cosine 768-dim + sparse IDF). Existing collections missing one of the
named vector configs are migrated automatically.

### `_init_qdrant(max_retries=10, wait=3)`

Connects to Qdrant with linear back-off retries and ensures the collection has the hybrid-search schema. If the collection does not exist it is created; if it exists but lacks named dense or sparse vector configs it is migrated (recreated or updated). Raises `RuntimeError` after all retries are exhausted.

Schema:

- `dense`: 768-dimensional cosine distance.
- `sparse`: IDF-modified sparse vectors for keyword search.

### `_tokenize(text)`

Splits text into lowercase word tokens using a `\b\w+\b` regex.

### `_token_to_index(token)`

Maps a token to a stable 32-bit integer index via the first 8 hex digits of its MD5 hash.

### `_build_sparse_vector(text)`

Builds a `SparseVector` from term-frequency counts. Tokenises the text via `_tokenize`, counts occurrences, maps each token to a stable integer index via `_token_to_index`, and returns a sparse vector suitable for BM25-style retrieval. Returns an empty vector when the text yields no tokens.

### `_build_point_vector(embedding, metadata)`

Combines a pre-computed dense embedding and a metadata-derived sparse vector (built from the `description` payload field) into a named-vector dict with keys `dense` and `sparse`.

### `insert_projects(embeddings, metadata_list, ids)`

Builds `PointStruct` entries with both dense and sparse vectors and upserts them in a single batch.
Sparse vectors are derived from the `description` field in each metadata dict.

### `delete_projects(ids)`

Deletes points by ID. No-op for an empty list.

### `search(query_vector, query_text="", limit=20, semantic_weight=0.7)`

Runs hybrid search and returns scored Qdrant points.

`semantic_weight` controls the search mode:

- `1.0`: pure dense (cosine) search.
- `0.0`: pure sparse (keyword) search.
- `0.0 < w < 1.0`: RRF fusion — dense and sparse results are fetched independently with
  prefetch limits proportional to `semantic_weight`, then fused via Qdrant's `FusionQuery(RRF)`.

RRF scores are rank-based and not bounded to [0, 1]; the FastAPI layer normalises them before returning results to clients.
