# FastAPI Utilities Module

Utility functions and classes for the FastAPI backend service, including data loading, embedding services, and pipeline management for semantic search functionality.

---

## Constants

### OLLAMA_URL
Default URL for Ollama service endpoint. Defaults to `"http://ollama:11434"`.

### EMBED_MODEL
Environment variable for specifying the embedding model to use. Retrieved from `MODEL` environment variable.

---

## Functions

### download_job

Triggers the data processing pipeline to download and process funding data.

#### Parameters

- `None`: This function takes no parameters.

#### Returns

- `None`: This function performs data processing but returns nothing.

#### Description

This function serves as an entry point for triggering the complete data processing pipeline. It:
- Prints status messages to indicate pipeline execution
- Calls `data_processing_pipeline()` to download, extract, clean, and prepare data
- Handles exceptions and reports failures
- Logs success or failure states

### chunked

Generator function that splits an iterable into chunks of specified size.

#### Parameters

- `iterable`: The iterable to split into chunks.
- `size` (int): The maximum size of each chunk.

#### Returns

- `generator`: Generator yielding lists of items, each of maximum `size` length.

#### Description

This utility function is used to process large datasets in manageable batches. It's particularly useful for:
- Processing large numbers of embeddings
- Handling batch operations efficiently
- Managing memory usage during data processing

### load_funding_data

Loads funding data from a Parquet file with retry logic.

#### Parameters

- `file_path` (str): Path to the Parquet file to load.
- `retries` (int, optional): Maximum number of retry attempts. Default is `10`.
- `delay` (int, optional): Initial delay between retries in seconds. Default is `1`.

#### Returns

- `pl.DataFrame`: Loaded Polars DataFrame containing funding data.

#### Description

This function loads funding data with built-in retry logic to handle cases where the file might not be immediately available (e.g., during concurrent processing). It:
- Attempts to read the Parquet file
- Retries on `FileNotFoundError` with exponential backoff
- Raises exception after maximum retries
- Logs retry attempts for monitoring

---

## Classes

### EmbeddingService

Handles text embedding generation using Ollama service with token-based chunking.

#### Constructor (__init__ method)

Initializes the embedding service with configuration parameters.

##### Parameters

- `ollama_url` (str, optional): URL of the Ollama service. Default is `OLLAMA_URL`.
- `model` (str, optional): Name of the embedding model to use. Default is `EMBED_MODEL`.
- `max_tokens` (int, optional): Maximum tokens per chunk. Default is `384`.
- `overlap_tokens` (int, optional): Overlap tokens between chunks. Default is `96`.
- `tokenizer` (str, optional): Hugging Face tokenizer identifier. Default is `"nomic-ai/nomic-embed-text-v1.5"`.

#### Methods

##### chunk_text

Splits text into overlapping token-based chunks using the tokenizer.

###### Parameters

- `text` (str): The text to chunk.

###### Returns

- `List[str]`: List of text chunks.

###### Description

This method implements token-based text chunking with overlap to ensure semantic continuity while respecting token limits. It:
- Encodes text using the configured tokenizer
- Splits into chunks of maximum `max_tokens` length
- Maintains overlap between consecutive chunks for context preservation
- Decodes token chunks back to text

##### fetch_embedding

Asynchronously fetches embedding vectors for a text chunk from Ollama.

###### Parameters

- `client` (httpx.AsyncClient): Async HTTP client for making requests.
- `text` (str): Text to embed.

###### Returns

- `Optional[List[float]]`: Embedding vector or None if request fails.

###### Description

This method makes asynchronous HTTP requests to the Ollama service to generate embeddings. It:
- Sends POST request to Ollama embeddings endpoint
- Handles HTTP errors gracefully
- Returns embedding vector or None on failure
- Includes timeout handling for network issues

---

# Pipeline

Main pipeline class responsible for embedding new project rows and inserting them into the Qdrant vector database.

---

## Constructor (__init__ method)
### Parameters

* `qdrant` (`QdrantManager`): Instance for interacting with the Qdrant database.
* `embed_service` (`EmbeddingService`): Service for generating embeddings from text.
* `file_path` (`str`): Path to the funding data file to process.

---

## Methods

### `manage_embeddings`

Orchestrates the complete embedding management workflow.

#### Parameters

* None

#### Returns

* `None`

#### Description

This is the main entry point for managing embeddings. It performs the following steps:

1. Loads funding data and normalizes UUIDs.
2. Fetches existing project IDs from Qdrant.
3. Deletes projects marked as deleted in the dataset.
4. Identifies new active projects not already in Qdrant.
5. Asynchronously generates embeddings for new projects and inserts them into Qdrant.
6. Logs all key steps and exits early if no new projects exist.

---

### `_load_and_normalize_data`

Loads the funding dataset and ensures UUIDs are in string format.

#### Parameters

* None

#### Returns

* `pl.DataFrame`: Polars DataFrame with UUIDs cast to UTF-8 strings.

#### Description

This method ensures consistent UUID formatting to prevent mismatches during database operations.

---

### `_delete_removed_projects`

Removes deleted projects from Qdrant that still exist in the database.

#### Parameters

* `df` (`pl.DataFrame`): The full funding data.
* `existing_ids` (`set[str]`): Set of existing project UUIDs in Qdrant.

#### Returns

* `None`

#### Description

Identifies rows marked as deleted in the dataset, intersects their UUIDs with existing Qdrant IDs, and deletes any matching projects. Logs the number of deleted projects.

---

### `_get_new_active_rows`

Filters for active projects not already present in Qdrant.

#### Parameters

* `df` (`pl.DataFrame`): The full funding data.
* `existing_ids` (`set[str]`): Set of existing project UUIDs in Qdrant.

#### Returns

* `pl.DataFrame`: DataFrame containing only new active projects.

#### Description

Filters out deleted projects and projects that already exist in the database, returning only rows that require embedding.

---

### `_embed_and_insert_rows`

Processes each new project by generating embeddings and inserting them into Qdrant.

#### Parameters

* `new_rows` (`pl.DataFrame`): DataFrame containing new active projects.

#### Returns

* `None`

#### Description

Iterates over project rows, extracts descriptions and metadata, and asynchronously generates embeddings for each project. Delegates per-project processing to `_process_single_project`.

---

### `_process_single_project`

Generates embeddings for a single project and inserts them into Qdrant.

#### Parameters

* `client` (`httpx.AsyncClient`): Shared HTTP client for embedding API calls.
* `description` (`str`): Project description text.
* `metadata` (`dict`): Project metadata dictionary.
* `project_id` (`str`): UUID of the project.

#### Returns

* `None`

#### Description

Splits the project description into text chunks, generates embeddings asynchronously, and inserts all valid embeddings into Qdrant. Logs a warning if no embeddings are generated.

---

### `_generate_embeddings`

Creates embeddings for a list of text chunks.

#### Parameters

* `client` (`httpx.AsyncClient`): HTTP client for embedding API.
* `chunks` (`list[str]`): Text chunks to embed.

#### Returns

* `list[list[float]]`: List of embedding vectors for each chunk.

#### Description

Generates embeddings asynchronously for each chunk. Only valid embeddings are returned, preserving the original order.

---

### `_insert_project_embeddings`

Inserts all embeddings for a project into Qdrant.

#### Parameters

* `embeddings` (`list[list[float]]`): List of embeddings for a project.
* `metadata` (`dict`): Project metadata.
* `project_id` (`str`): UUID of the project.

#### Returns

* `None`

#### Description

Stores each embedding as a separate entry in Qdrant, while sharing the same metadata and project ID. Supports multiple chunks per project.

---

### `_fetch_existing_ids`

Fetches all project UUIDs currently stored in Qdrant.

#### Parameters

* None

#### Returns

* `List[str]`: List of project UUIDs.

#### Description

Scrolls through the Qdrant collection using pagination to retrieve all existing project IDs. Includes error handling and logging.

---

## Data Flow

The pipeline follows this sequence:
1. Load funding data from Parquet file
2. Normalize UUIDs for consistency
3. Identify existing projects in Qdrant
4. Handle deleted projects (remove from Qdrant)
5. Process new active projects:
   - Chunk text descriptions
   - Generate embeddings for each chunk
   - Insert embeddings into Qdrant with metadata
6. Log progress and completion status
