# Semantic Funding Search (SeFuSe)

**Find matching funding programs for your project - fully local, fully private.**

SeFuSe searches funding programs from the [Federal Funding Database](https://www.foerderdatenbank.de/FDB/DE/Home/home.html) (Förderdatenbank des Bundes) and the [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis) using AI (an embedding model) - no cloud, no data sharing.

---

## What is SeFuSe?

SeFuSe lets you **describe your project in plain language** and returning the funding programs that are the best match - ranked by relevance, with a short summary and a direct link.

**Key properties:**

- **Fully local** - the AI model and all data run on your own machine. Nothing is sent to OpenAI, Google, or any external service.
- **Bilingual** - handles German and English text natively.
- **Hybrid search** - combines semantic understanding (what your project *means*) with keyword matching (specific terms), so you get good results even with short or vague descriptions.
- **Self-updating** - the system automatically refreshes funding data from the source databases on a configurable schedule.

A short demo video is available here: [▶ YouTube Video](https://youtu.be/wau3Kw_P8QQ)

---

## Motivation

SeFuSe was developed in response to an urgent practical need: staff in transfer centres, researchers, and other users who regularly need to identify suitable funding programs were spending significant time manually browsing large databases with limited search capabilities.

Comparable tools rely on **OpenAI’s Custom GPTs** or similar cloud-based services. This means project ideas and research descriptions are routinely sent to commercial third parties. SeFuSe avoids this entirely — when operated on local infrastructure, **no data leaves the system**. There are no calls to external APIs beyond fetching the funding datasets themselves, and no long-term data storage. The model, the vectors, and the search all run on your own hardware.

The goal is to make the search for relevant funding simpler and more accessible, particularly for institutions that handle sensitive project ideas or operate under data protection constraints.

---

## Quick Start

[>>> Read the Docs](https://to82lod.gitpages.uni-jena.de/sefuse/)

This guide walks you through getting SeFuSe running from scratch. No prior experience with Docker or Coding is required.

### Step 1 - Install the prerequisites

You need two free tools installed on your computer before you begin:

**Git** - used to download the project code.
Download and install it from [git-scm.com](https://git-scm.com/install/). Accept all defaults during installation.

**Docker Desktop** - runs all the services (database, AI model, web interface) in isolated containers so nothing interferes with the rest of your system.
Download and install it from [docs.docker.com/desktop](https://docs.docker.com/desktop/#products-inside-docker-desktop). Once installed, open Docker Desktop and wait until it shows "Engine running" in the bottom left corner before continuing.

> **Windows users:** Docker Desktop requires WSL 2 (Windows Subsystem for Linux). The installer will prompt you to enable it if it is not already active. Follow the on-screen instructions and restart your computer if asked.

---

### Step 2 - Download the project

Open a terminal (on Windows: search for "Command Prompt" or "PowerShell" in the Start menu) and run:

```bash
git clone https://github.com/trholy/sefuse
cd sefuse
```

This downloads the project into a folder called `sefuse` and moves you into it.

---

### Step 3 - Create your configuration file

SeFuSe needs a configuration file called `.env` with your personal secrets (passwords, API tokens). A template is included. Copy it:

**Linux / macOS:**
```bash
cp .env.example .env
```

**Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Now open `.env` in any text editor (Notepad works fine) and replace the three placeholder values:

| Line in `.env` | What to change | Example |
|---|---|---|
| `POSTGRES_PASSWORD=change_me_db_password` | Replace with any password for the internal database. You will not need to type this manually. | `POSTGRES_PASSWORD=change_me_db_password` |
| `ADMIN_PASSWORD=change_me_admin_password` | Replace with the password you want to use to log in to the web interface. | `ADMIN_PASSWORD=change_me_admin_password` |
| `INTERNAL_API_TOKEN=change_me_to_a_random_secret` | Replace with a long random string. This is an internal security token - it does not need to be memorable. | `INTERNAL_API_TOKEN=change_me_to_a_random_secret` |

Everything else in `.env` can be left at its default value to get started.

> **Important:** SeFuSe will refuse to start if any of these three values still start with `change_me`. This is intentional - it prevents accidentally running with insecure defaults.

---

### Step 4 - Start the system

In your terminal (still inside the `sefuse` folder), run:

```bash
docker-compose up --build
```

This command builds all service images and starts them. **The first start takes time** - typically 10 to 30 minutes depending on your internet speed and hardware, because:

- Docker downloads the base images for each service (~several GB total)
- The AI embedding model (`bge-m3`, ~1.2 GB) is downloaded from the internet
- Python dependencies are installed inside the containers
- The funding datasets are fetched from the source databases and indexed

You will see a stream of log output in the terminal. This is normal. The system is ready when you see log lines indicating that FastAPI is serving requests and Streamlit has started.

> **Subsequent starts** (without `--build`) are much faster - usually under a minute - because everything is already downloaded and built.

---

### Step 5 - Open the web interface

Once the system is running, open your browser and go to:

**[http://localhost:8080](http://localhost:8080)**

Log in with:
- **Username:** `admin` (or whatever you set as `ADMIN_USERNAME` in `.env`)
- **Password:** the `ADMIN_PASSWORD` you chose in Step 3

You will land on the search page. Type a description of your project or research area and hit **Search**. Results are ranked by relevance and include a short summary and a direct link to the funding program.

---

### Stopping the system

To stop all services, press `Ctrl+C` in the terminal where `docker-compose up` is running. To also remove the containers (but keep your data), run:

```bash
docker-compose down
```

Your indexed data and downloaded model are stored in the `./data/` and `./ollama/data/` folders and will survive a restart.

---

## How the System Works

The five services interact across three Docker networks (`backend`, `frontend`, `egress`). Here is the full data flow from raw source data to a search result:

### Indexing (runs at startup and on schedule)

1. **FastAPI** triggers the data processing pipeline (German or EU). For German funding, the raw Parquet ZIP is downloaded from the Federal Funding Database CDN. For EU funding, open and forthcoming calls are fetched page-by-page from the EU Funding & Tenders Portal API.
2. **FastAPI** cleans and transforms the raw data: HTML is stripped, fields are extracted, each program receives a deterministic UUID, and the result is written to a Parquet file with a taxonomy JSON sidecar.
3. **FastAPI** reads the Parquet file and splits each program description into text chunks. Documents under `ADAPTIVE_CHUNK_THRESHOLD` tokens (default 600) are kept as a single chunk. Longer documents are split into 512-token windows with 62-token overlap, snapped to the last sentence boundary in the trailing quarter to avoid mid-sentence cuts.
4. Each chunk is prepended with a contextual header (`Title: ...\nFunding area: ...\n\n`) so it is self-contained for retrieval. **FastAPI** sends all chunks for one project in a single batched embed request to **Ollama** (`bge-m3`, 1024-dim dense vector).
5. **FastAPI** also builds a sparse BM25-style vector for each chunk: stopwords (German + English) are removed, German Snowball stemming and compound splitting are applied, term frequencies are BM25-saturated (`k1=1.2`), and token indices are hashed via MD5.
6. Each chunk is stored in **Qdrant** as its own point with a deterministic UUID5 ID (`uuid5(project_uuid, "chunk_{i}")`), carrying both `dense` and `sparse` named vectors plus the project metadata as payload. Stale points from removed programs are cleaned up via a payload filter on `project_uuid`.

### Search (per user query)

7. **Streamlit** sends the user's query and parameters (limit, `semantic_weight`, taxonomy filters) to **FastAPI** over the internal Docker network, authenticated via `X-Internal-Token`.
8. **FastAPI** embeds the query text with **Ollama** using the same model and no special prefix (`bge-m3` is symmetric — documents and queries are embedded identically).
9. **FastAPI** asks **Qdrant** to run a **Convex Combination hybrid search**: dense cosine similarity and sparse BM25 results are fetched independently via prefetch, min-max normalised per branch, then combined as `score = w × dense_norm + (1−w) × sparse_norm` where `w` is `semantic_weight`.
10. **FastAPI** aggregates the chunk-level Qdrant results by `project_uuid` using **TopK-Avg**: the top-3 chunk scores per project are averaged into a single project score.
11. Scores are normalised to [0, 1] relative to the highest-scoring project in the result set.
12. Taxonomy filters and the optional drop-N/A filter are applied server-side. Results are sorted by descending score and truncated to the requested `limit`.
13. **Streamlit** renders the results: score, title, short description, metadata, and a direct link to the funding program's detail page.

### Data persistence

All indexed data survives container restarts through Docker volumes:

| Volume | Contents |
|---|---|
| `./data/qdrant` | All Qdrant collections — dense and sparse vectors plus payloads |
| `./data/funding_data` | Processed Parquet files and taxonomy JSON sidecars |
| `./ollama/data` | Downloaded `bge-m3` model weights |
| `./data/postgres` | User accounts and bcrypt hashes |

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

Three Docker networks enforce network isolation:

| Network    | Type     | Members                          | Purpose                                        |
|------------|----------|----------------------------------|------------------------------------------------|
| `backend`  | internal | FastAPI, Qdrant, Postgres, Ollama | Internal service communication; no internet access |
| `frontend` | bridge   | FastAPI, Streamlit               | Streamlit ↔ FastAPI; required for host port binding |
| `egress`   | bridge   | FastAPI, Ollama                  | Controlled outbound internet for API calls and model pulls |

---

## Service Breakdown

### Qdrant (Vector Database)

```yaml
qdrant:
  image: qdrant/qdrant
  volumes:
    - ./data/qdrant:/qdrant/storage
```

Qdrant stores all embedding vectors and metadata using a hybrid schema (dense cosine 1024-dim + sparse IDF-modified BM25 vectors). Convex Combination fusion blends both signal types at query time.

* **Persistent storage:** `./data/qdrant`
* **Internal only:** Qdrant is not exposed on the host - only reachable by FastAPI inside the Docker backend network.
* **Payload indexes:** Keyword indexes on `project_uuid` and taxonomy key fields accelerate filter queries

This ensures that embeddings survive container restarts.

---

### Ollama (Local Embedding Model)

```yaml
ollama:
  build: ./ollama
  volumes:
    - ./ollama/data:/home/ollama/.ollama
  environment:
    - MODEL=bge-m3
```

Ollama runs the embedding model locally as the non-root `ollama` user.
The model is downloaded and cached in `./ollama/data`.
The startup script (`init_models.sh`) pulls the model if not already present, then execs `ollama serve` as PID 1 for clean signal handling.

#### Environment variables

| Variable | Purpose                                                       |
| -------- | ------------------------------------------------------------- |
| `MODEL`  | Name of the embedding model to load (e.g. `bge-m3`) |

This value must match the `MODEL` used by FastAPI and Streamlit.

---

### FastAPI (Backend & Scheduler)

```yaml
fastapi:
  build:
    context: .
    dockerfile: fastapi/Dockerfile
  volumes:
    - ./data/funding_data:/app/data
    - ./data_processing/src:/app/data_processing:ro
  depends_on:
    ollama:
      condition: service_healthy
  read_only: true
  tmpfs:
    - /tmp
    - /home/appuser:uid=10001,gid=10001,mode=0700
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
    - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
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
| `EU_API_KEY`                          | API key for the EU Funding & Tenders Portal search API. `SEDIA` is the public key. |
| `EU_MAX_PAGES`                        | Maximum pages fetched from the EU API per run (default `100`) |
| `INTERNAL_API_TOKEN`                  | Shared secret between FastAPI and Streamlit. Required at startup (see [Security notes](#security-notes)). |
| `ALLOW_UNAUTHENTICATED_INTERNAL_API`  | Set `true` to skip token auth in local dev. Logs a warning. |


---

### Streamlit (Web UI)

```yaml
streamlit:
  build:
    context: .
    dockerfile: streamlit/Dockerfile
  ports:
    - "0.0.0.0:8080:8501"
  volumes:
    - ./data/funding_data:/app/data:ro
  depends_on:
    fastapi:
      condition: service_healthy
    postgres:
      condition: service_healthy
  read_only: true
  tmpfs:
    - /tmp
    - /home/appuser:uid=10001,gid=10001,mode=0700
  environment:
    - MODEL=bge-m3
    - FASTAPI_URL=http://fastapi:8000
    - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
    - DB_HOST=postgres
    - DB_PORT=5432
    - DB_NAME=${POSTGRES_DB}
    - DB_USER=${POSTGRES_USER}
    - DB_PASSWORD=${POSTGRES_PASSWORD}
    - AUTH_ENABLED=${AUTH_ENABLED}
    - ADMIN_USERNAME=${ADMIN_USERNAME}
    - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    - SESSION_TIMEOUT_MINUTES=${SESSION_TIMEOUT_MINUTES:-30}
    - BCRYPT_ROUNDS=${BCRYPT_ROUNDS:-12}
    - PASSWORD_MIN_LENGTH=${PASSWORD_MIN_LENGTH:-8}
```

Streamlit provides the **user interface** where users enter project descriptions and view matching funding programs.

#### Environment variables

| Variable                   | Purpose                                                          |
| -------------------------- | ---------------------------------------------------------------- |
| `MODEL`                    | Must match FastAPI and Ollama                                    |
| `FASTAPI_URL`              | Internal URL of the FastAPI service                              |
| `INTERNAL_API_TOKEN`       | Shared secret for authenticating requests to FastAPI             |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL connection for login and user storage |
| `DB_CONNECT_TIMEOUT_SECONDS` | Seconds before a DB connection attempt times out (default `5`) |
| `AUTH_ENABLED`             | Enables/disables Streamlit authentication globally (default `true`) |
| `ADMIN_USERNAME`           | Predefined admin account (created at app startup)                |
| `ADMIN_PASSWORD`           | Admin password (stored as bcrypt hash in DB)                     |
| `SESSION_TIMEOUT_MINUTES`  | Idle session expiry in minutes (default `30`)                    |
| `BCRYPT_ROUNDS`            | bcrypt cost factor for password hashing (default `12`)           |
| `PASSWORD_MIN_LENGTH`      | Minimum character length for user passwords (default `8`)        |

---

## Security Notes

### Required secrets

Before running for the first time, copy `.env.example` to `.env` and replace all `change_me_*` placeholder values. FastAPI and Streamlit refuse to start with placeholder secrets - this is enforced at import time.

| Variable | Requirement |
|---|---|
| `INTERNAL_API_TOKEN` | Arbitrary secret shared by FastAPI and Streamlit. Use a random 32+ character string. |
| `ADMIN_PASSWORD` | Admin account password. Must not start with `change_me`. |
| `DB_PASSWORD` / `POSTGRES_PASSWORD` | PostgreSQL password. Must not start with `change_me`. |

For local development without a token, set `ALLOW_UNAUTHENTICATED_INTERNAL_API=true` in `.env`. This logs a startup warning.

### Read-only filesystem

FastAPI and Streamlit run with `read_only: true` - the container filesystem is mounted read-only. Writable paths are provided via in-memory `tmpfs` mounts:

| Path | Purpose |
|---|---|
| `/tmp` | Temporary files (e.g., downloads, pip cache) |
| `/home/appuser` | HuggingFace tokenizer cache (`~/.cache/huggingface/`), written on first startup |

---

## EU API Key

`SEDIA` is the public key for the [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis). It may be subject to rate limits.

When `EU_API_KEY=SEDIA`, a startup warning is logged by the EU pipeline.

---

## Authentication

Authentication is handled entirely by Streamlit and backed by PostgreSQL. FastAPI itself is not user-facing and is protected by a shared internal token (`INTERNAL_API_TOKEN`) that Streamlit attaches to every backend request — it is never exposed to end-users.

### User login

All Streamlit pages require a valid session. Users log in with a username and password on the landing page. There is no self-registration — accounts are created by an admin. Sessions expire after `SESSION_TIMEOUT_MINUTES` (default 30) minutes of inactivity.

### Passwords

Passwords are hashed with **bcrypt** before storage. The cost factor is configurable via `BCRYPT_ROUNDS` (default `12`). Requirements at creation or password change:

- Minimum `PASSWORD_MIN_LENGTH` characters (default `8`)
- Maximum 64 characters (hard limit — bcrypt silently truncates beyond 72 bytes)
- No character class requirements (no forced uppercase, digit, or symbol)

The login flow performs a constant-time bcrypt check even for unknown usernames to prevent timing-based user enumeration.

### Roles and admin account

Two roles exist: `admin` and `user`. The admin account is bootstrapped automatically on first start from `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`. If the account already exists its password is updated to match `.env` on every restart, so changing `ADMIN_PASSWORD` and restarting the stack resets the admin credential.

Admins have access to the **Admin User Management** page where they can create, deactivate, and delete user accounts and reset passwords. Regular users only see the search pages.

### Disabling authentication

Set `AUTH_ENABLED=false` in `.env` to bypass authentication entirely. All pages become accessible without login. Intended for local development only.

---

## A Note on Development

This project was developed with **LLM assistance** and also served as a hands-on exploration of the so-called *vibe coding* phenomenon — a style of development where large language models take on a significant share of the implementation work while the developer steers, reviews, and validates the output.

Code and documentation have been reviewed, but **this project is not production-ready**. There is no guarantee that it is free of bugs, inefficiencies, or security vulnerabilities. It is shared as a functional prototype and learning exercise, not as hardened software suitable for deployment in critical or public-facing environments.

Contributions are welcome.

---

## Acknowledgements

This project builds upon the data collected by **jstet** and **pr130**, creators of the  
**[Funding Scraper](https://github.com/CorrelAid/cdl_funding_scraper/)** project.

Their work on scraping and providing structured funding data forms the foundation of this project.  
