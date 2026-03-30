# `fastapi.utils.qdrant_utils`

Wraps basic dense-vector Qdrant collection management and CRUD-style vector operations.

## Module Constants

- `VECTOR_DB_HOST`: Qdrant host.
- `QDRANT_PORT`: Qdrant port.

## Class `QdrantManager`

### Constructor

- `host`: Qdrant host name.
- `port`: Qdrant service port.
- `collection_name`: target collection name.

The constructor immediately initializes the Qdrant client and ensures the collection exists.

### `_init_qdrant(max_retries=10, wait=3)`

Retries connection to Qdrant until the service becomes available or raises `RuntimeError`.

If the target collection does not exist, it creates one with:

- vector size `768`
- cosine distance

### `insert_projects(embeddings, metadata_list, ids)`

Builds `PointStruct` entries and upserts them into the configured collection.

### `delete_projects(ids)`

Deletes points by ID and returns immediately when the input list is empty.

### `search(query_vector, limit=20)`

Runs dense-vector search and returns the resulting Qdrant points.
