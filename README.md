# Semantic Funding Search (SeFuSe)

**Semantic search for funding programs in the [Federal Funding Database](https://www.foerderdatenbank.de/FDB/DE/Home/home.html) (Förderdatenbank des Bundes) and the [Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis) of the European Union.**

---

## Overview

[Read the Docs.](https://to82lod.gitpages.uni-jena.de/sefuse/)

**SeFuSe** is a tool for **semantic search of funding programs** in Funding Databases.

The idea: users enter their **project description** into a web interface and automatically receive **matching funding programs**, including a short description and a direct link to the funding database.

A short demo is available here: [▶ YouTube Video](https://youtu.be/wau3Kw_P8QQ)

## Quick Start

Before you begin, make sure you have the following installed on your system:

* [Git](https://git-scm.com/install/)
* [Docker Desktop](https://docs.docker.com/desktop/#products-inside-docker-desktop)

Then run the following commands:

```bash
git clone https://github.com/trholy/sefuse
cd sefuse
docker-compose up --build
```

The build process may take several minutes, as required services need to be downloaded and installed.

Once the setup is complete, you can access the Streamlit web interface at:
[http://localhost:8501](http://localhost:8501)

---

## How It Works

The system is based on an embedding model and a **vector database**, which is regularly populated with new programs from the funding database.

### Pipeline

1. **Retrieval of funding programs** from the funding database (regularly updated).
2. **Extraction & preprocessing** of descriptions — HTML cleaning, field extraction, UUID assignment, Parquet + taxonomy JSON output.
3. **Embedding pipeline** — adaptive chunking (short documents stay whole, long documents are split at sentence boundaries), contextual headers (title + funding area), dense embedding via Ollama (`bge-m3`), BM25-saturated sparse vectors with German Snowball stemming and compound splitting. Each chunk is stored as its own Qdrant point with both dense and sparse vectors.
4. **User input**: A project description is entered via the web interface.
5. **Hybrid search**: Convex Combination (CC) fusion blends dense (semantic) and sparse (keyword) scores, weighted by a user-adjustable slider. Results are aggregated per project using TopK-Avg scoring.
6. **Output**: Matching programs with scores, metadata, and direct links to the funding database.

---

## Motivation

Comparable projects rely on **OpenAI’s Custom GPTs**.
This means that project ideas are regularly sent to commercial providers such as OpenAI.
With SeFuSe, you can run your **entire setup locally** - your data remains on your own server.

---

## Docker Compose Installation & Configuration

SeFuSe is designed to run as a fully self-contained, local AI system using **Docker Compose**.
It orchestrates five services:

| Service       | Role                                                   |
| ------------- | ------------------------------------------------------ |
| **PostgreSQL**| User/authentication database                           |
| **Qdrant**    | Vector database for storing and searching embeddings   |
| **Ollama**    | Local LLM runtime for generating embeddings            |
| **FastAPI**   | Backend API for data processing, embedding, and search |
| **Streamlit** | Web UI for semantic search                             |

All services communicate over Docker’s internal network using service names (e.g. `qdrant`, `ollama`, `fastapi`).

---

## Service Breakdown

### Qdrant (Vector Database)

```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"
  volumes:
    - ./data/qdrant:/qdrant/storage
```

Qdrant stores all embedding vectors and metadata using a hybrid schema (dense cosine 768-dim + sparse IDF-modified BM25 vectors). Convex Combination fusion blends both signal types at query time.

* **Persistent storage:** `./data/qdrant`
* **Port 6333:** Used by FastAPI for similarity search
* **Payload indexes:** Keyword indexes on `project_uuid` and taxonomy key fields accelerate filter queries

This ensures that embeddings survive container restarts.

---

### Ollama (Local Embedding Model)

```yaml
ollama:
  build: ./ollama
  ports:
    - "11434:11434"
  volumes:
    - ./ollama/data:/root/.ollama
  environment:
    - MODEL=bge-m3
```

Ollama runs the embedding model locally.
The model is downloaded and cached in `./ollama/data`.

#### Environment variables

| Variable | Purpose                                                       |
| -------- | ------------------------------------------------------------- |
| `MODEL`  | Name of the embedding model to load (e.g. `bge-m3`) |

This value must match the `MODEL` used by FastAPI and Streamlit.

---

### FastAPI (Backend & Scheduler)

```yaml
fastapi:
  build: ./fastapi
  ports:
    - "8000:8000"
  volumes:
    - ./data/funding_data:/app/data
    - ./data_processing/src:/app/data_processing
  depends_on:
    - qdrant
    - ollama
  environment:
    - MODEL=bge-m3
    - TOKENIZER=BAAI/bge-m3
    - CRON_TRIGGER_GERMAN_DATA_PROCESSING=0
    - CRON_TRIGGER_GERMAN_EMBEDDING=3
    - CRON_TRIGGER_EU_DATA_PROCESSING=1
    - CRON_TRIGGER_EU_EMBEDDING=4
    - OLLAMA_URL=http://ollama:11434
    - VECTOR_DB_HOST=qdrant
    - QDRANT_PORT=6333
```

FastAPI is the **brain of the system**. It:

* Downloads funding data
* Processes and cleans it
* Generates embeddings via Ollama
* Stores and queries vectors in Qdrant
* Exposes APIs for Streamlit

#### Environment variables

| Variable                              | Meaning                                              |
|---------------------------------------|------------------------------------------------------|
| `MODEL`                               | Embedding model name (must match Ollama + Streamlit) |
| `TOKENIZER`                           | HuggingFace tokenizer used for chunking text         |
| `CRON_TRIGGER_GERMAN_DATA_PROCESSING` | Hour (0–23) when German funding data is refreshed    |
| `CRON_TRIGGER_GERMAN_EMBEDDING`       | Hour (0–23) when German embeddings are refreshed     |
| `CRON_TRIGGER_EU_DATA_PROCESSING`     | Hour (0–23) when EU funding data is refreshed        |
| `CRON_TRIGGER_EU_EMBEDDING`           | Hour (0–23) when EU embeddings are refreshed         |
| `OLLAMA_URL`                          | Internal Ollama API endpoint                         |
| `VECTOR_DB_HOST`                      | Qdrant hostname inside Docker                        |
| `QDRANT_PORT`                         | Qdrant service port                                  |
| `BM25_K1`                             | BM25 saturation parameter (default `1.2`)            |
| `ADAPTIVE_CHUNK_THRESHOLD`            | Token count below which docs stay as one chunk (default `600`) |
| `TOPK_SCORES`                         | Top-K chunk scores averaged per project (default `3`) |
| `EMBEDDING_CONCURRENCY`               | Number of projects embedded in parallel (default `4`) |
| `OLLAMA_EMBED_TIMEOUT_SECONDS`        | Per-request embedding timeout in seconds (default `120`) |
| `OLLAMA_MODEL_READY_INTERVAL`         | Seconds between Ollama readiness probes on startup (default `10`) |
| `OLLAMA_MODEL_READY_TIMEOUT`          | Max seconds to wait for Ollama before skipping embeddings (default `600`) |
| `EU_API_KEY`                          | API key for the EU Funding & Tenders Portal search API. `SEDIA` is the [public demo key](https://api.tech.ec.europa.eu/search-api/prod/rest/swagger-ui.html). |
| `EU_MAX_PAGES`                        | Maximum pages fetched from the EU API per run (default `100`) |

Example:

```
CRON_TRIGGER_GERMAN_DATA_PROCESSING=0  → German data refresh at midnight
CRON_TRIGGER_GERMAN_EMBEDDING=3        → German embeddings at 03:00
CRON_TRIGGER_EU_DATA_PROCESSING=1      → EU data refresh at 01:00
CRON_TRIGGER_EU_EMBEDDING=4            → EU embeddings at 04:00
```

---

### Streamlit (Web UI)

```yaml
streamlit:
  build: ./streamlit
  ports:
    - "8501:8501"
  volumes:
    - ./data/funding_data:/app/data
  depends_on:
    - fastapi
  environment:
    - MODEL=bge-m3
    - FASTAPI_URL=http://fastapi:8000
    - DB_HOST=postgres
    - DB_PORT=5432
    - DB_NAME=${POSTGRES_DB}
    - DB_USER=${POSTGRES_USER}
    - DB_PASSWORD=${POSTGRES_PASSWORD}
    - AUTH_ENABLED=${AUTH_ENABLED}
    - ADMIN_USERNAME=${ADMIN_USERNAME}
    - ADMIN_PASSWORD=${ADMIN_PASSWORD}
```

Streamlit provides the **user interface** where users enter project descriptions and view matching funding programs.

#### Environment variables

| Variable         | Purpose                                           |
| ---------------- | ------------------------------------------------- |
| `MODEL`          | Must match FastAPI and Ollama                     |
| `FASTAPI_URL`    | Internal URL of the FastAPI service               |
| `DB_*`           | PostgreSQL connection for login and user storage  |
| `AUTH_ENABLED`   | Enables/disables Streamlit authentication globally |
| `ADMIN_USERNAME` | Predefined admin account (created at app startup) |
| `ADMIN_PASSWORD` | Admin password (stored as bcrypt hash in DB)      |

---

## Authentication

SeFuSe uses a simple username/password login for Streamlit access.

- No self-registration is available.
- All pages require successful login.
- Passwords are stored as bcrypt hashes in PostgreSQL.
- An admin account is created from `.env` values and can manage users in the **Admin User Management** page.
- Set `AUTH_ENABLED=false` to bypass authentication entirely.

---

## How the System Works Together

1. **Ollama** runs the embedding model (`bge-m3`, 1024-dim multilingual)
2. **FastAPI** chunks documents (adaptive thresholding + sentence-boundary snapping), embeds via Ollama, and builds BM25-saturated sparse vectors with German stemming + compound splitting
3. **FastAPI** stores both dense and sparse vectors in **Qdrant** as named vectors per point
4. **Streamlit** sends search queries to **FastAPI**
5. **FastAPI** embeds the query, performs Convex Combination hybrid search in **Qdrant**, aggregates chunks per project (TopK-Avg), normalizes scores, and applies taxonomy filters
6. Results are returned to **Streamlit**

All data and models persist on disk through Docker volumes.

---

## Start the System

From the project root:

```bash
docker-compose up --build
```

Then open:

* **Streamlit UI:** [http://localhost:8501](http://localhost:8501)
* **FastAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Qdrant UI:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## Project Structure

This repository is with clear separation between data storage, data processing, backend services, and user-facing applications.

### Core Directories

* **data/**
  Central location for persisted data used across services.

  * `funding_data/` – Raw and processed funding datasets.
  * `qdrant/` – Persistent storage for the Qdrant vector database.

* **data_processing/**
  Contains the data ingestion and transformation pipeline responsible for preparing funding data.

  * `src/` – Application source code following a clean `src` layout.

    * `config/` – Centralized configuration handling.
    * `processing/` – Core data transformation logic for German and EU funding data.
    * `utils/` – Helper utilities for fetching, downloading, and extracting source data.
    * `eu_funding_main.py` – Entry point for the EU funding workflow.
    * `german_funding_main.py` – Entry point for the German funding workflow.
  * `requirements.txt` – Python dependencies for the data processing service.

* **fastapi/**
  FastAPI-based backend service that exposes APIs and interacts with Qdrant and processed data.

  * `src/` – Backend application code.

    * `main.py` – API entry point.
    * `utils/` – FastAPI and Qdrant helper utilities.
  * `requirements.txt` – Backend dependencies.
  * `Dockerfile` – Container definition for the API service.

* **streamlit/**
  Streamlit-powered frontend application for exploring and visualizing funding data.

  * `src/` – Streamlit application code.

    * `Home.py` – Main landing page.
    * `pages/` – Streamlit page entry points for German and EU search.
    * `ui/` – Reusable page classes and rendering logic.
    * `utils/` – UI and data access helpers.
  * `requirements.txt` – Frontend dependencies.
  * `Dockerfile` – Container definition for the Streamlit app.

* **ollama/**
  Contains Docker configuration and initialization scripts for local model serving.

  * `init_models.sh` – Script for downloading and initializing models.
  * `data/` – Persistent model data.

* **docs/**
  Project documentation built with MkDocs, structured to mirror the codebase modules.

```
./
├── .dockerignore
├── .env.example
├── .gitignore
├── .gitlab-ci.yml
├── LICENSE
├── README.md
├── THIRD_PARTY_LICENSES.txt
├── data
│   ├── funding_data
│   │   ├── .gitkeep
│   ├── postgres
│   │   ├── .gitkeep
│   └── qdrant
│       ├── .gitkeep
├── data_processing
│   ├── data
│   │   └── .gitkeep
│   ├── requirements.txt
│   └── src
│       ├── config
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── eu_constants.py
│       ├── eu_funding_main.py
│       ├── german_funding_main.py
│       ├── processing
│       │   ├── __init__.py
│       │   ├── cleaner.py
│       │   ├── common_data_pipeline.py
│       │   ├── eu_funding_processor.py
│       │   ├── german_funding_processor.py
│       │   ├── taxonomy_contract_builder.py
│       │   ├── uuid_generator.py
│       │   └── value_extractor.py
│       └── utils
│           ├── __init__.py
│           ├── eu_funding_fetcher.py
│           ├── extractor.py
│           └── german_funding_fetcher.py
├── docker-compose.yml
├── docs
│   ├── data_processing
│   │   ├── config
│   │   │   └── config.md
│   │   ├── eu_funding_main.md
│   │   ├── german_funding_main.md
│   │   ├── processing
│   │   │   ├── cleaner.md
│   │   │   ├── common_data_pipeline.md
│   │   │   ├── eu_funding_processor.md
│   │   │   ├── german_funding_processor.md
│   │   │   ├── taxonomy_contract_builder.md
│   │   │   ├── uuid_generator.md
│   │   │   └── value_extractor.md
│   │   └── utils
│   │       ├── eu_funding_fetcher.md
│   │       ├── extractor.md
│   │       └── german_funding_fetcher.md
│   ├── fastapi
│   │   ├── main.md
│   │   └── utils
│   │       ├── fastapi_utils.md
│   │       └── qdrant_utils.md
│   ├── shared
│   │   └── taxonomy_contract.md
│   └── streamlit
│       ├── Home.md
│       ├── auth
│       │   ├── handlers.md
│       │   ├── migrate.md
│       │   └── services.md
│       ├── pages
│       │   ├── 1_Federal_Funding_Database.md
│       │   ├── 2_EU_Funding_Programs.md
│       │   └── 3_Admin_User_Management.md
│       ├── ui
│       │   └── search_pages.md
│       └── utils
│           └── utils.md
├── fastapi
│   ├── Dockerfile
│   ├── data
│   │   └── .gitkeep
│   ├── requirements.txt
│   └── src
│       ├── main.py
│       └── utils
│           ├── __init__.py
│           ├── fastapi_utils.py
│           └── qdrant_utils.py
├── mkdocs.yml
├── ollama
│   ├── Dockerfile
│   ├── data
│   │   ├── .gitkeep
│   └── init_models.sh
├── project_structure.py
├── shared
│   ├── __init__.py
│   └── taxonomy_contract.py
├── streamlit
│   ├── .streamlit
│   │   └── config.toml
│   ├── Dockerfile
│   ├── data
│   │   └── .gitkeep
│   ├── favicon.jpg
│   ├── migrations
│   │   └── 001_auth_schema.sql
│   ├── requirements.txt
│   └── src
│       ├── Home.py
│       ├── auth
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── constants.py
│       │   ├── db.py
│       │   ├── exceptions.py
│       │   ├── handlers.py
│       │   ├── migrate.py
│       │   ├── models.py
│       │   ├── protocols.py
│       │   ├── repository.py
│       │   ├── security.py
│       │   ├── services.py
│       │   └── session.py
│       ├── pages
│       │   ├── 1_Federal_Funding_Database.py
│       │   ├── 2_EU_Funding_Programs.py
│       │   └── 3_Admin_User_Management.py
│       ├── ui
│       │   ├── __init__.py
│       │   └── search_pages.py
│       └── utils
│           ├── __init__.py
│           └── utils.py
└── tests
    ├── __init__.py
    ├── _helpers
    │   ├── __init__.py
    │   └── module_loader.py
    ├── test_data_processing
    │   ├── __init__.py
    │   ├── test_common_pipeline.py
    │   ├── test_eu_processor_fetcher.py
    │   ├── test_io_utils.py
    │   ├── test_main_pipelines.py
    │   └── test_processing_core.py
    ├── test_fastapi
    │   ├── __init__.py
    │   ├── test_fastapi_utils.py
    │   ├── test_main.py
    │   └── test_qdrant_utils.py
    └── test_streamlit
        ├── __init__.py
        ├── test_search_pages.py
        └── test_utils.py
```

---

## Acknowledgements

This project builds upon the data collected by **jstet** and **pr130**, creators of the  
**[Funding Scraper](https://github.com/CorrelAid/cdl_funding_scraper/)** project.

Their work on scraping and providing structured funding data forms the foundation of this project.  
