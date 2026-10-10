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
- **Saved searches, watchlist and alerts** - save a search, bookmark programs, and be told when a new program matches a saved search.

A short demo video is available here: [▶ YouTube Video](https://youtu.be/wau3Kw_P8QQ)

---

## Motivation

SeFuSe was developed in response to an urgent practical need: staff in transfer centres, researchers, and other users who regularly need to identify suitable funding programs were spending significant time manually browsing large databases with limited search capabilities.

Comparable tools rely on **OpenAI’s Custom GPTs** or similar cloud-based services. This means project ideas and research descriptions are routinely sent to commercial third parties. SeFuSe avoids this entirely — when operated on local infrastructure, **no data leaves the system**. There are no calls to external APIs beyond fetching the funding datasets themselves. The model, the vectors, and the search all run on your own hardware. A search query is stored only if a user saves it as a saved search, and then only in the local database. The one optional exception is push notifications: if you switch on Gotify, the titles of matching programs and of the saved search are sent to the Gotify server you configured.

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

Now open `.env` in any text editor (Notepad works fine) and replace the four placeholder values:

| Line in `.env` | What to change | Example |
|---|---|---|
| `POSTGRES_PASSWORD=change_me_db_password` | Replace with any password for the internal database. You will not need to type this manually. | `POSTGRES_PASSWORD=change_me_db_password` |
| `ADMIN_PASSWORD=change_me_admin_password` | Replace with the password you want to use to log in to the web interface. | `ADMIN_PASSWORD=change_me_admin_password` |
| `INTERNAL_API_TOKEN=change_me_to_a_random_secret` | Replace with a long random string. This is an internal security token - it does not need to be memorable. | `INTERNAL_API_TOKEN=change_me_to_a_random_secret` |
| `QDRANT_API_KEY=change_me_qdrant_api_key` | Replace with another long random string. It protects the internal vector database - it does not need to be memorable either. | `QDRANT_API_KEY=change_me_qdrant_api_key` |

Everything else in `.env` can be left at its default value to get started.

> **Important:** SeFuSe will refuse to start if any of these four values still start with `change_me`. This is intentional - it prevents accidentally running with insecure defaults.

---

### Step 4 - Prepare the data folders (Linux only)

**Skip this step on Windows and macOS** - Docker Desktop handles it for you.

On Linux, run this once before the first start:

```bash
sudo ./setup.sh
```

The services run as non-root users inside their containers, and Linux keeps the folders you
just cloned owned by your own user account. Without this step the database and the embedding
model cannot write to their folders, and you will see `Permission denied` errors on startup.
The script creates the four data folders and hands each one to the right user.

---

### Step 5 - Start the system

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

### Step 6 - Open the web interface

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

## Saved Searches, Watchlist and Alerts

Each user has their own saved searches, watchlist and alert inbox.

- **Watchlist** - every search result has an **Add to Watchlist** checkbox. The **Watchlist** page lists the bookmarked programs, grouped into Federal and EU funding, with a link to each.
- **Saved searches** - after a search, **Save Search** stores the query together with its filters, semantic weight and result limit. The **Saved Searches** page lists them; **Restore** reopens the search page with the same settings.
- **Alerts** - an alert can be enabled per saved search. Once a day (`ALERT_CHECK_HOUR`, default 05:00 UTC) SeFuSe checks the programs that are new since the alert was enabled and notifies you about those that match.

A new program counts as a match when it passes the saved search's filters, would rank among the top existing programs for the saved query, and scores above what deliberately off-topic probe queries reach in that collection. How high it must rank is the alert's level:

| Level | A new program must rank among the saved query's |
|---|---|
| Broad | top 25 existing programs |
| Balanced (default) | top 10 |
| Strict | top 3 |

Matches appear under **Alert Matches** on the Saved Searches page. A program is announced once per saved search, and near-copies of an already indexed program do not alert. Alerts are judged on the semantic (dense) similarity only.

Optionally, matches are also pushed through a self-hosted [Gotify](https://gotify.net) server - see [Push notifications (Gotify)](#push-notifications-gotify). Set `ALERTS_ENABLED=false` to switch alerts off entirely; saved searches and the watchlist keep working.

---

## How the System Works

The five services interact across three Docker networks (`backend`, `frontend`, `egress`). Here is the full data flow from raw source data to a search result:

### Indexing (runs at startup and on schedule)

1. **FastAPI** triggers the data processing pipeline (German or EU). For German funding, the CSV that CorrelAid's [fdb_scraper](https://github.com/CorrelAid/fdb_scraper) publishes weekly from the Federal Funding Database is downloaded, with a fallback to the last downloaded copy if the host is unavailable. For EU funding, open and forthcoming calls are fetched page-by-page from the EU Funding & Tenders Portal API.
2. **FastAPI** cleans and transforms the raw data: HTML is stripped, fields are extracted, each program receives a deterministic UUID, and the result is written to a Parquet file with a taxonomy JSON sidecar. A refresh whose row count drops by more than `DATA_REFRESH_MAX_DROP_RATIO` is refused, so a truncated download is not read as programs being withdrawn.
3. **FastAPI** reads the Parquet file and splits each program description into text chunks. Documents under `ADAPTIVE_CHUNK_THRESHOLD` tokens (default 600) are kept as a single chunk. Longer documents are split into 512-token windows with 62-token overlap, snapped to the last sentence boundary in the trailing quarter to avoid mid-sentence cuts.
4. Each chunk is prepended with a contextual header (title, funding type, funding area, eligible applicants, keywords and summary, where stated) so it is self-contained for retrieval. **FastAPI** sends all chunks for one project in a single batched embed request to **Ollama** (`bge-m3`, 1024-dim dense vector).
5. **FastAPI** also builds a sparse BM25-style vector for each chunk, analysed in the collection's own language. German funding: German + English stopwords are removed, then German Snowball stemming and compound splitting. EU funding (English-only text): English stopwords and English Snowball stemming, with no compound splitting — English compounds are space-separated, and the German fugen splitter only produces noise on them. Either way, term frequencies are BM25-saturated (`k1=1.2`) and token indices are hashed via MD5.
6. Each chunk is stored in **Qdrant** as its own point with a deterministic UUID5 ID (`uuid5(project_uuid, "chunk_{i}")`), carrying both `dense` and `sparse` named vectors plus the project metadata as payload. Stale points from removed programs are cleaned up via a payload filter on `project_uuid`. A program whose text changed is re-embedded, and one whose displayed fields changed has its payload rewritten without a new embedding.

### Search (per user query)

7. **Streamlit** sends the user's query and parameters (limit, `semantic_weight`, taxonomy filters) to **FastAPI** over the internal Docker network, authenticated via `X-Internal-Token`.
8. **FastAPI** embeds the query text with **Ollama** using the same model and no special prefix (`bge-m3` is symmetric — documents and queries are embedded identically).
9. **FastAPI** asks **Qdrant** to run a **Convex Combination hybrid search**: dense cosine similarity and sparse BM25 results are fetched independently via prefetch, min-max normalised per branch, then combined as `score = w × dense_norm + (1−w) × sparse_norm` where `w` is `semantic_weight`.
10. **FastAPI** aggregates the chunk-level Qdrant results by `project_uuid` using **TopK-Avg**: the top-3 chunk scores per project are averaged into a single project score.
11. Taxonomy filters and the optional drop-N/A filter are applied server-side.
12. The scores that survive filtering are normalised to [0, 1] against the best remaining match, and returned as `relative_score`. Results are sorted by descending score and truncated to the requested `limit`. Filtering before normalising matters: the other order scales the list against a programme the filter just removed.
13. **FastAPI** also returns a `weak_match` flag. Because `relative_score` is relative, the top result always reads 100% — even for a query no programme really answers. The flag compares the query's best similarity anywhere in the collection against what deliberately off-topic probe queries reach there, so the UI can say when a result list is "the closest available" rather than relevant.
14. **Streamlit** renders the results: relevance, title, short description, metadata, and a direct link to the funding program's detail page — with a warning above the list when `weak_match` is set.

#### Query language and the keyword channel

German funding programmes are described in German, EU calls in English, and each collection's sparse
index is built in that language. You can search either collection in either language, but the two
channels do not behave the same way across languages:

- **Dense (semantic)** uses `bge-m3`, which is multilingual. It bridges German ↔ English, so a German
  query still finds relevant English EU calls.
- **Sparse (keyword)** is BM25 over hashed tokens and is monolingual by construction. It cannot match
  a German query term against an English document, whatever the stemmer does.

So querying in the *other* language leaves the keyword half contributing almost nothing, and the
result is carried by the dense vector alone — at the default `semantic_weight` of 0.7 that is roughly
30% of the score doing little work. **For the best results, describe your project in the language of
the funding source**: German for the Förderdatenbank, English for EU calls. Lowering
`semantic_weight` toward pure keyword search only helps when your query language matches the corpus.

### Data persistence

All indexed data survives container restarts through Docker volumes:

| Volume | Contents | Owner UID on Linux |
|---|---|---|
| `./data/qdrant` | All Qdrant collections — dense and sparse vectors plus payloads | `0` |
| `./data/funding_data` | Processed Parquet files and taxonomy JSON sidecars | `10001` |
| `./ollama/data` | Downloaded `bge-m3` model weights | `999` |
| `./data/postgres` | User accounts and bcrypt hashes, login sessions, saved searches, watchlists, alert matches and first-seen timestamps | `70` |

On Linux these are bind mounts, so they keep host ownership and must be owned by the UID of
the non-root user inside each container — that is what `sudo ./setup.sh` sets up (Step 4).
Docker Desktop on Windows and macOS handles it transparently.

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
  image: qdrant/qdrant:v1.18
  environment:
    - QDRANT__TELEMETRY_DISABLED=true
    - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
  volumes:
    - ./data/qdrant:/qdrant/storage
```

Qdrant stores all embedding vectors and metadata using a hybrid schema (dense cosine 1024-dim + sparse IDF-modified BM25 vectors). Convex Combination fusion blends both signal types at query time.

* **Persistent storage:** `./data/qdrant`
* **Internal only:** Qdrant is not exposed on the host - only reachable by FastAPI inside the Docker backend network.
* **API key:** requests must carry `QDRANT_API_KEY`, which FastAPI sends. Telemetry is switched off.
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
    - CRON_TRIGGER_GERMAN_DATA_PROCESSING=${CRON_TRIGGER_GERMAN_DATA_PROCESSING:-0}
    - CRON_TRIGGER_GERMAN_EMBEDDING=${CRON_TRIGGER_GERMAN_EMBEDDING:-3}
    - CRON_TRIGGER_EU_DATA_PROCESSING=${CRON_TRIGGER_EU_DATA_PROCESSING:-1}
    - CRON_TRIGGER_EU_EMBEDDING=${CRON_TRIGGER_EU_EMBEDDING:-4}
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
| `ALERTS_ENABLED`                      | Master switch for saved-search alerts (default `true`). `false` switches the feature off entirely: no nightly check job, no alert inbox, no sidebar badge, no alert controls in the UI, and every `ALERT_*`/`GOTIFY_*` setting below is ignored. Saved searches keep working. |
| `ALERT_CHECK_HOUR`                    | Hour (0–23, UTC) of the daily saved-search alert check (default `5`) |
| `ALERT_NOTIFICATION_RETENTION_DAYS`   | Days an alert match stays in the in-app inbox before it is pruned (default `30`) |
| `ALERT_LEVEL_RULES`                   | Optional JSON `{"level": k}` overriding how many top existing programmes a new one must rank among (default Broad 25, Balanced 10, Strict 3) |
| `ALERT_NOISE_MARGIN`                  | How far above the best off-topic canary cosine a new programme must score to alert (default 0.04) |
| `FIRST_SEEN_BURST_MIN` / `FIRST_SEEN_BURST_RATIO` | Re-key guard: a larger burst of "new" programmes is stamped as legacy (default 25 / 0.1) |
| `DUPLICATE_COSINE`                    | Cosine at which a new programme counts as a near-duplicate and never alerts (default 0.97) |
| `OLLAMA_URL`                          | Internal Ollama API endpoint                         |
| `VECTOR_DB_HOST`                      | Qdrant hostname inside Docker                        |
| `QDRANT_PORT`                         | Qdrant service port                                  |
| `QDRANT_API_KEY`                      | API key FastAPI sends to Qdrant. Must not start with `change_me`; if left empty, Qdrant runs without authentication and FastAPI logs a warning (see [Security notes](#security-notes)). |
| `VECTOR_DIMENSION`                    | Dense vector size; must match the embedding model (default `1024` for `bge-m3`) |
| `BM25_K1`                             | BM25 saturation parameter (default `1.2`)            |
| `ADAPTIVE_CHUNK_THRESHOLD`            | Token count below which docs stay as one chunk (default `600`) |
| `TOPK_SCORES`                         | Top-K chunk scores averaged per project (default `3`) |
| `EMBEDDING_CONCURRENCY`               | Number of projects embedded in parallel (default `4`) |
| `OLLAMA_EMBED_TIMEOUT_SECONDS`        | Per-request embedding timeout in seconds (default `120`) |
| `OLLAMA_MODEL_READY_INTERVAL`         | Seconds between Ollama readiness probes on startup (default `10`) |
| `OLLAMA_MODEL_READY_TIMEOUT`          | Max seconds to wait for Ollama before skipping embeddings (default `600`) |
| `EU_API_KEY`                          | API key for the EU Funding & Tenders Portal search API (`SEDIA`). |
| `EU_MAX_PAGES`                        | Maximum pages fetched from the EU API per run (default `100`). Reaching it aborts the fetch. |
| `DATA_REFRESH_MAX_DROP_RATIO`         | How far the row count may fall against the previous run before a refresh is refused (default `0.2`) |
| `LOG_LEVEL`                           | Log level for FastAPI and Streamlit: `DEBUG`, `INFO`, `WARNING` or `ERROR` (default `INFO`) |
| `INTERNAL_API_TOKEN`                  | Shared secret between FastAPI and Streamlit. Required at startup (see [Security notes](#security-notes)). |
| `ALLOW_UNAUTHENTICATED_INTERNAL_API`  | Set `true` to skip token auth in local dev. Logs a warning. |

All of these can be set in `.env`; `docker-compose.yml` passes them through with the defaults shown.

#### Push notifications (Gotify)

Saved-search alerts always land in the in-app inbox. They can additionally be pushed to users' devices through a [Gotify](https://gotify.net) server that you run yourself. Push is off by default.

| Variable                 | Meaning                                              |
|--------------------------|------------------------------------------------------|
| `GOTIFY_ENABLED`         | `true` switches push on (default `false`)            |
| `GOTIFY_URL`             | Base URL of your Gotify server, e.g. `https://gotify.example.com` or `http://192.168.1.20:8080`. A server on your own network is fine. |
| `GOTIFY_SECRET_KEY`      | Fernet key that encrypts users' Gotify tokens in the database. Required when push is on. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Rotating it invalidates every stored token. |
| `GOTIFY_PRIORITY`        | Default message priority, 0-10 (default `5`)         |
| `GOTIFY_TIMEOUT_SECONDS` | HTTP timeout for calls to Gotify (default `10`)      |

Each user then pastes their own Gotify *application token* on the Notification Settings page. With push on, the titles of matching programmes and of the saved search are sent to that Gotify server.


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
| `SESSION_COOKIES_ENABLED`  | Keeps a login across browser tabs and page reloads through a session cookie; `false` requires a login per tab (default `true`) |
| `SESSION_COOKIE_SECURE`    | Adds the `Secure` attribute to the session cookie; set `true` behind TLS (default `false`) |
| `LOGIN_LOCKOUT_MAX_ATTEMPTS` | Consecutive failed logins before an account is temporarily locked (default `5`) |
| `LOGIN_LOCKOUT_DURATION_MINUTES` | How long such a lock lasts, in minutes (default `15`)        |

---

## Security Notes

### Required secrets

Before running for the first time, copy `.env.example` to `.env` and replace all `change_me_*` placeholder values. FastAPI and Streamlit refuse to start with placeholder secrets - this is enforced at import time.

| Variable | Requirement |
|---|---|
| `INTERNAL_API_TOKEN` | Arbitrary secret shared by FastAPI and Streamlit. Use a random 32+ character string. |
| `QDRANT_API_KEY` | API key for the internal Qdrant database. Use a random 32+ character string. Must not start with `change_me`; an empty value leaves Qdrant unauthenticated. |
| `ADMIN_PASSWORD` | Admin account password. Must not start with `change_me`. |
| `DB_PASSWORD` / `POSTGRES_PASSWORD` | PostgreSQL password. Must not start with `change_me`. |
| `GOTIFY_SECRET_KEY` | Only when `GOTIFY_ENABLED=true`: Fernet key that encrypts users' Gotify tokens. |

For local development without a token, set `ALLOW_UNAUTHENTICATED_INTERNAL_API=true` in `.env`. This logs a startup warning.

### Read-only filesystem

FastAPI and Streamlit run with `read_only: true` - the container filesystem is mounted read-only. Writable paths are provided via in-memory `tmpfs` mounts:

| Path | Purpose |
|---|---|
| `/tmp` | Temporary files (e.g., downloads, pip cache) |
| `/home/appuser` | HuggingFace tokenizer cache (`~/.cache/huggingface/`), written on first startup |

---

## EU API Key

`SEDIA` is the API key documented for the [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis) search API. It is the value to use — no registration or replacement is needed; keep `EU_API_KEY=SEDIA` as shipped in `.env.example`.

---

## Authentication

Authentication is handled entirely by Streamlit and backed by PostgreSQL. FastAPI itself is not user-facing and is protected by a shared internal token (`INTERNAL_API_TOKEN`) that Streamlit attaches to every backend request — it is never exposed to end-users.

### User login

All Streamlit pages require a valid session. Users log in with a username and password on the landing page. There is no self-registration — accounts are created by an admin. Sessions expire after `SESSION_TIMEOUT_MINUTES` (default 30) minutes of inactivity.

A login is kept across browser tabs and page reloads through a session cookie backed by the database. Set `SESSION_COOKIES_ENABLED=false` to require a login per tab, and `SESSION_COOKIE_SECURE=true` when serving SeFuSe over HTTPS.

After `LOGIN_LOCKOUT_MAX_ATTEMPTS` consecutive failed logins (default 5) an account is locked for `LOGIN_LOCKOUT_DURATION_MINUTES` (default 15).

### Passwords

Passwords are hashed with **bcrypt** before storage. The cost factor is configurable via `BCRYPT_ROUNDS` (default `12`). Requirements at creation or password change:

- Minimum `PASSWORD_MIN_LENGTH` characters (default `8`)
- Maximum 64 characters (hard limit — bcrypt silently truncates beyond 72 bytes)
- No character class requirements (no forced uppercase, digit, or symbol)

The login flow performs a constant-time bcrypt check even for unknown usernames to prevent timing-based user enumeration.

### Roles and admin account

Two roles exist: `admin` and `user`. The admin account is bootstrapped automatically on first start from `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`. If the account already exists its password is updated to match `.env` on every restart, so changing `ADMIN_PASSWORD` and restarting the stack resets the admin credential.

Admins have access to the **Admin User Management** page where they can create, deactivate, and delete user accounts and reset passwords. A deactivated account cannot log in. Regular users see the search pages, their Watchlist and Saved Searches, the How to Use page and - when push notifications are switched on - Notification Settings.

### Disabling authentication

Set `AUTH_ENABLED=false` in `.env` to bypass authentication entirely. All pages become accessible without login. Intended for local development only.

---

## A Note on Development

This project was developed with **LLM assistance** and also served as a hands-on exploration of the so-called *vibe coding* phenomenon — a style of development where large language models take on a significant share of the implementation work while the developer steers, reviews, and validates the output.

Code and documentation have been reviewed, but **this project is not production-ready**. There is no guarantee that it is free of bugs, inefficiencies, or security vulnerabilities. It is shared as a functional prototype and learning exercise, not as hardened software suitable for deployment in critical or public-facing environments.

Contributions are welcome.

---

## Acknowledgements

This project builds upon the data collected by **jstet**, creator of the  
**[fdb-scraper](https://github.com/CorrelAid/fdb_scraper)** project.

His work on scraping and providing structured funding data forms the foundation of this project.  
