# Qdrant Manager Module

Utility class for managing interactions with the Qdrant vector database. This module handles database initialization, data insertion, deletion, and search operations for the semantic funding search system.

---

## QdrantManager

Main class for managing Qdrant vector database operations including initialization, data management, and search functionality.

### Constructor (__init__ method)

Initializes the Qdrant manager with connection parameters.

#### Parameters

- `host` (str, optional): Host address of the Qdrant service. Default is `"qdrant"`.
- `port` (int, optional): Port number for Qdrant service. Default is `6333`.
- `collection_name` (str, optional): Name of the Qdrant collection to use. Default is `"fundings"`.

### Methods

#### _init_qdrant

Internal method that initializes and connects to the Qdrant service with retry logic.

##### Parameters

- `max_retries` (int, optional): Maximum number of connection retry attempts. Default is `10`.
- `wait` (int, optional): Wait time between retries in seconds. Default is `3`.

##### Returns

- `QdrantClient`: Initialized Qdrant client instance.

##### Description

This method:
1. Attempts to establish connection to Qdrant service
2. Tests connection with `get_collections()` call
3. Implements retry logic with exponential backoff
4. Creates collection if it doesn't exist
5. Configures collection with 768-dimensional cosine distance vectors
6. Logs connection status and collection creation

##### Error Handling

- Retries connection attempts up to `max_retries` times
- Raises `RuntimeError` if connection cannot be established
- Handles connection timeouts and service unavailability

#### insert_projects

Inserts multiple project records into the Qdrant collection.

##### Parameters

- `embeddings` (List[List[float]]): List of embedding vectors for each project.
- `metadata_list` (List[Dict[str, Any]]): List of metadata dictionaries for each project.
- `ids` (List[str]): List of unique identifiers for each project.

##### Returns

- `None`: This method performs database operations but returns nothing.

##### Description

This method:
1. Creates `PointStruct` objects combining embeddings, metadata, and IDs
2. Inserts all points into the Qdrant collection using `upsert`
3. Logs successful insertion count
4. Handles batch insertion of multiple projects

##### Data Structure

Each project is stored as a point with:
- `id`: String representation of project ID
- `vector`: 768-dimensional embedding vector
- `payload`: Metadata dictionary containing project information

#### delete_projects

Deletes project records from the Qdrant collection.

##### Parameters

- `ids` (List[str]): List of project IDs to delete.

##### Returns

- `None`: This method performs database operations but returns nothing.

##### Description

This method:
1. Checks if there are IDs to delete
2. Uses Qdrant's `delete` method to remove specified points
3. Logs successful deletion count
4. Handles empty deletion lists gracefully

#### search

Performs vector similarity search in the Qdrant collection.

##### Parameters

- `query` (List[float]): Query embedding vector for similarity search.
- `limit` (int, optional): Maximum number of results to return. Default is `20`.

##### Returns

- `List[PointStruct]`: List of search results containing matching points.

##### Description

This method:
1. Performs similarity search using the provided query vector
2. Returns top `limit` most similar results
3. Uses cosine distance for similarity calculation
4. Returns raw Qdrant point structures for further processing

---

## Data Schema

### Point Structure

Each stored project consists of:
- **ID**: String identifier (UUID)
- **Vector**: 768-dimensional embedding vector
- **Payload**: Dictionary containing project metadata including:
  - Project title
  - Descriptions (short and full)
  - Funding information
  - Dates
  - Categories and classifications
