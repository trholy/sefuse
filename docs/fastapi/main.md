# FastAPI Main Module

Main FastAPI application for the semantic funding search system. This module provides the REST API endpoints and orchestrates the complete search pipeline including data processing, embedding, and vector search.

---

## Constants

### OLLAMA_URL
Default URL for Ollama service endpoint. Defaults to `"http://ollama:11434"`.

### EMBED_MODEL
Environment variable for specifying the embedding model to use. Retrieved from `MODEL` environment variable.

### TOKENIZER
Environment variable for specifying the tokenizer to use. Retrieved from `TOKENIZER` environment variable.

### CRON_TRIGGER_DATA_PROCESSING

Environment variable for specifying the time to run the data processing pipline. Retrieved from `CRON_TRIGGER_DATA_PROCESSING` environment variable.

### CRON_TRIGGER_EMBEDDING

Environment variable for specifying the time to run the embedding pipline. Retrieved from `CRON_TRIGGER_EMBEDDING` environment variable.

### EXTRACTED_FILE_PATH
Path to the processed funding data file containing UUIDs. Default is `"data/parquet_data_uuid.parquet"`.

---

## Application Lifecycle

### lifespan

Async context manager that handles application startup and shutdown procedures.

#### Startup Process

1. **Initial Data Processing**: Runs data processing pipeline to download and prepare funding data
2. **Initial Embedding Pipeline**: Runs embedding pipeline to create vector representations
3. **Periodic Job Scheduling**: Sets up scheduled jobs for:
   - Data processing every day at specified hour (`CRON_TRIGGER_DATA_PROCESSING` environment variable)
   - Embedding pipeline execution very day at specified hour (`CRON_TRIGGER_EMBEDDING` environment variable)

#### Shutdown Process

- Stops the scheduler and cleans up resources

---

## Services Initialization

### QdrantManager
Manages connection to and operations with the Qdrant vector database.

### EmbeddingService
Handles text embedding generation using Ollama service with token-based chunking.

### Pipeline
Main pipeline for embedding new data and inserting into Qdrant.

## API Endpoints

### POST /v1/search

Performs semantic search on funding projects using vector similarity.

#### Request Body

```json
{
  "model": "string",
  "messages": [
    {
      "role": "user",
      "content": "string"
    }
  ],
  "limit": integer
}
```

#### Parameters

- `model` (str): Name of the embedding model to use
- `messages` (List[Dict]): List of messages (only first message used)
- `limit` (int): Maximum number of search results to return

#### Response

```json
{
  "matches": [
    {
      "project_id": "string",
      "project_title": "string",
      "project_short_description": "string",
      "project_full_description": "string",
      "on_website_from": "string",
      "last_updated": "string",
      "funding_type": ["string"],
      "funding_area": ["string"],
      "funding_location": ["string"],
      "eligible_applicants": ["string"],
      "project_website": "string",
      "matching_score": float
    }
  ]
}
```

#### Processing Steps

1. **Query Embedding**: Generates embedding vector for user query using Ollama
2. **Vector Search**: Searches Qdrant for similar projects using cosine similarity
3. **Result Aggregation**: Groups multiple embeddings per project into single results
4. **Score Aggregation**: Takes maximum score for relevance ranking
5. **Response Formatting**: Structures results with consistent metadata format
