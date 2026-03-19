# Semantic Funding Search (SeFuSe)

**Semantic search for funding programs in the Federal Funding Database (Förderdatenbank des Bundes).**

---

## Overview

[Read the Docs.](https://to82lod.gitpages.uni-jena.de/sefuse/)

**SeFuSe** is a tool for **semantic search of funding programs** in the Federal Funding Database.

The idea: users enter their **project description** into a web interface and automatically receive **matching funding programs**, including a short description and a direct link to the funding database.

A short demo is available here: [▶ YouTube Video](https://youtu.be/wau3Kw_P8QQ)

---

Here’s a cleaner, more polished version with clearer flow and tone:

---

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
2. **Extraction & preprocessing** of short descriptions for semantic search.
3. **User input**: A project description is entered via the web interface.
4. **Semantic search**: The system identifies relevant funding programs.
5. **Output**: Matching programs with links to the corresponding funding database entries.

---

## Motivation

Comparable projects rely on **OpenAI’s Custom GPTs**.
This means that project ideas are regularly sent to commercial providers such as OpenAI.
With SeFuSe, you can run your **entire setup locally** - your data remains on your own server.

---

## Docker Compose Installation & Configuration

SeFuSe is designed to run as a fully self-contained, local AI system using **Docker Compose**.
It orchestrates four services:

| Service       | Role                                                   |
| ------------- | ------------------------------------------------------ |
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

Qdrant stores all embedding vectors and metadata.

* **Persistent storage:** `./data/qdrant`
* **Port 6333:** Used by FastAPI for similarity search

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
    - MODEL=nomic-embed-text
```

Ollama runs the embedding model locally.
The model is downloaded and cached in `./ollama/data`.

#### Environment variables

| Variable | Purpose                                                       |
| -------- | ------------------------------------------------------------- |
| `MODEL`  | Name of the embedding model to load (e.g. `nomic-embed-text`) |

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
    - MODEL=nomic-embed-text
    - TOKENIZER=nomic-ai/nomic-embed-text-v1.5
    - CRON_TRIGGER_DATA_PROCESSING=0
    - CRON_TRIGGER_EMBEDDING=4
    - DOWNLOAD_FILE=https://...
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

| Variable                       | Meaning                                              |
| ------------------------------ | ---------------------------------------------------- |
| `MODEL`                        | Embedding model name (must match Ollama + Streamlit) |
| `TOKENIZER`                    | HuggingFace tokenizer used for chunking text         |
| `CRON_TRIGGER_DATA_PROCESSING` | Hour (0–23) when funding data is refreshed           |
| `CRON_TRIGGER_EMBEDDING`       | Hour (0–23) when new embeddings are generated        |
| `DOWNLOAD_FILE`                | URL of the funding dataset (Parquet ZIP)             |
| `OLLAMA_URL`                   | Internal Ollama API endpoint                         |
| `VECTOR_DB_HOST`               | Qdrant hostname inside Docker                        |
| `QDRANT_PORT`                  | Qdrant service port                                  |

Example:

```
CRON_TRIGGER_DATA_PROCESSING=0   → run at midnight
CRON_TRIGGER_EMBEDDING=4        → run at 04:00 AM
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
    - MODEL=nomic-embed-text
    - FASTAPI_URL=http://fastapi:8000
```

Streamlit provides the **user interface** where users enter project descriptions and view matching funding programs.

#### Environment variables

| Variable      | Purpose                             |
| ------------- | ----------------------------------- |
| `MODEL`       | Must match FastAPI and Ollama       |
| `FASTAPI_URL` | Internal URL of the FastAPI service |

---

## How the System Works Together

1. **Ollama** runs the embedding model
2. **FastAPI** sends text chunks to Ollama and receives vectors
3. **FastAPI** stores vectors in **Qdrant**
4. **Streamlit** sends search queries to **FastAPI**
5. **FastAPI** performs vector search in **Qdrant**
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
    * `processing/` – Core data transformation logic (cleaning, UUID generation, value extraction).
    * `utils/` – Helper utilities for downloading and extracting data.
    * `main.py` – Entry point for running the data processing workflow.
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

    * `app.py` – Main dashboard entry point.
    * `utils/` – UI and data access helpers.
  * `requirements.txt` – Frontend dependencies.
  * `Dockerfile` – Container definition for the Streamlit app.

* **ollama/**
  Contains Docker configuration and initialization scripts for local model serving.

  * `init_models.sh` – Script for downloading and initializing models.
  * `data/` – Persistent model data.

* **docs/**
  Project documentation built with MkDocs, structured to mirror the codebase.

```
./
├── .dockerignore
├── .gitignore
├── .gitlab-ci.yml
├── LICENSE
├── README.md
├── THIRD_PARTY_LICENSES.txt
├── data
│   ├── funding_data
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
│       │   └── config.py
│       ├── main.py
│       ├── processing
│       │   ├── __init__.py
│       │   ├── cleaner.py
│       │   ├── uuid_generator.py
│       │   └── value_extractor.py
│       └── utils
│           ├── __init__.py
│           ├── downloader.py
│           └── extractor.py
├── docker-compose.yml
├── docs
│   ├── data_processing
│   │   ├── config
│   │   │   └── config.md
│   │   ├── main.md
│   │   ├── processing
│   │   │   ├── cleaner.md
│   │   │   ├── uuid_generator.md
│   │   │   └── value_extractor.md
│   │   └── utils
│   │       ├── downloading.md
│   │       └── extractor.md
│   ├── fastapi
│   │   ├── main.md
│   │   └── utils
│   │       ├── fastapi_utils.md
│   │       └── qdrant_utils.md
│   └── streamlit
│       ├── app.md
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
└── streamlit
    ├── Dockerfile
    ├── data
    │   └── .gitkeep
    ├── requirements.txt
    └── src
        ├── app.py
        └── utils
            ├── __init__.py
            └── utils.py
```

---

## Acknowledgements

This project builds upon the data collected by **jstet** and **pr130**, creators of the  
**[Funding Scraper](https://github.com/CorrelAid/cdl_funding_scraper/)** project.

Their work on scraping and providing structured funding data forms the foundation of this project.  
