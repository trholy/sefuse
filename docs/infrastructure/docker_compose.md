# Docker Compose

`docker-compose.yml` defines all five SeFuSe services and the networks that connect them. Start the entire stack with:

```bash
docker-compose up --build
```

---

## Networks

| Network | Driver | Internal | Purpose |
|---|---|---|---|
| `frontend` | bridge | no | Streamlit ↔ FastAPI communication. Non-internal so the host `ports:` binding on Streamlit works. |
| `backend` | bridge | yes | FastAPI ↔ Qdrant / Postgres / Ollama. No outbound internet, no host access. |
| `egress` | bridge | no | Controlled outbound internet for services that call external APIs. Only FastAPI and Ollama are attached. |

---

## Services

### `qdrant`

Vector database for hybrid (dense + sparse) search.

| Property | Value                                                                           |
|---|---------------------------------------------------------------------------------|
| Image | `qdrant/qdrant:v1.18`                                                           |
| Container | `sefuse_qdrant`                                                                 |
| Exposed port | `6333` (internal only)                                                          |
| Volume | `./data/qdrant:/qdrant/storage`                                                 |
| Networks | `backend`                                                                       |
| Healthcheck | `curl -f http://localhost:6333/healthz` — 10 s interval, 5 s timeout, 5 retries |
| Restart | on-failure, max 5 attempts                                                      |
| Resource limits | 2 GB RAM, 1.0 CPU                                                               |
| Security | `no-new-privileges:true`                                                        |

### `postgres`

PostgreSQL database for user authentication.

| Property | Value |
|---|---|
| Build | `./postgres` |
| Container | `sefuse_postgres` |
| Exposed port | `5432` (internal only) |
| Volume | `./data/postgres:/var/lib/postgresql/data` |
| Networks | `backend` |
| Healthcheck | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` — 10 s interval, 5 s timeout, 5 retries |
| Restart | on-failure, max 5 attempts |
| Resource limits | 512 MB RAM, 1.0 CPU |
| Security | `no-new-privileges:true` |

Required environment variables:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

### `ollama`

Local embedding model server (default model: `bge-m3`).

| Property | Value |
|---|---|
| Build | `./ollama` |
| Container | `sefuse_ollama` |
| Exposed port | `11434` (internal only) |
| Volume | `./ollama/data:/home/ollama/.ollama` |
| Networks | `backend`, `egress` |
| Healthcheck | `ollama list` — 10 s interval, 5 s timeout, 10 retries |
| Restart | on-failure, max 5 attempts |
| Resource limits | 2 GB RAM, 2.0 CPU |
| Security | `no-new-privileges:true` |

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `bge-m3` | Embedding model to pull and serve. Must match FastAPI and Streamlit. |
| `OLLAMA_READY_TIMEOUT` | `60` | Seconds `init_models.sh` waits for `ollama serve` to become ready before failing. |
| `OLLAMA_KEEP_ALIVE` | `-1` | Keep model loaded indefinitely in memory. |
| `NVIDIA_VISIBLE_DEVICES` | `all` | Uncomment GPU options in the compose file to use NVIDIA GPU acceleration. |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | Required NVIDIA driver capabilities for GPU mode. |
| `OLLAMA_NUM_CTX` | `2048` | Context window size. Relevant when using GPU mode. |

To enable GPU acceleration, uncomment the `gpus` block and the NVIDIA environment variables in `docker-compose.yml`.

### `fastapi`

Backend API: data pipelines, embedding generation, hybrid search, cron scheduling.

| Property | Value |
|---|---|
| Build context | `.` (repo root), `fastapi/Dockerfile` |
| Container | `sefuse_fastapi` |
| Exposed port | `8000` (internal only) |
| Networks | `backend`, `frontend`, `egress` |
| Depends on | `qdrant` (healthy), `ollama` (healthy) |
| Healthcheck | `curl -f http://localhost:8000/health` — 30 s interval, 5 s timeout, 3 retries |
| Restart | on-failure, max 5 attempts |
| Resource limits | 1 GB RAM, 1.0 CPU |
| Security | `no-new-privileges:true`, `read_only: true` |
| Tmpfs | `/tmp`, `/home/appuser` (uid=10001, mode=0700) |

Volumes:

| Mount | Mode | Purpose |
|---|---|---|
| `./data/funding_data:/app/data` | read-write | Processed Parquet files and taxonomy JSON written by pipelines. |
| `./data_processing/src:/app/data_processing` | read-only | Data-processing source code volume-mounted for pipeline access. |

The `/home/appuser` tmpfs covers the HuggingFace tokenizer cache (`~/.cache/huggingface/`) written at startup when `AutoTokenizer.from_pretrained` runs.

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `bge-m3` | Embedding model name — must match Ollama and Streamlit. |
| `TOKENIZER` | `BAAI/bge-m3` | HuggingFace tokenizer identifier. |
| `INTERNAL_API_TOKEN` | — | Shared secret required by `InternalTokenMiddleware`. |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama base URL. |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `120` | Per-request HTTP timeout for embedding calls. |
| `OLLAMA_MODEL_READY_TIMEOUT` | `600` | Max seconds to wait for Ollama model readiness on startup. |
| `OLLAMA_MODEL_READY_INTERVAL` | `10` | Seconds between model readiness probe retries. |
| `VECTOR_DB_HOST` | `qdrant` | Qdrant hostname. |
| `QDRANT_PORT` | `6333` | Qdrant port. |
| `GERMAN_COLLECTION_NAME` | `fundings_german` | Qdrant collection for German funding data. |
| `EU_COLLECTION_NAME` | `fundings_eu` | Qdrant collection for EU funding data. |
| `GERMAN_EXTRACTED_FILE_PATH` | `data/german_parquet_data_uuid.parquet` | Path to UUID-enriched German Parquet. |
| `EU_EXTRACTED_FILE_PATH` | `data/eu_parquet_data_uuid.parquet` | Path to UUID-enriched EU Parquet. |
| `GERMAN_TAXONOMY_FILE_PATH` | `data/taxonomy_german.json` | Path to German taxonomy contract artifact. |
| `CRON_TRIGGER_GERMAN_DATA_PROCESSING` | `0` | Hour of day for German data-processing cron. |
| `CRON_TRIGGER_GERMAN_EMBEDDING` | `3` | Hour of day for German embedding cron. |
| `CRON_TRIGGER_EU_DATA_PROCESSING` | `1` | Hour of day for EU data-processing cron. |
| `CRON_TRIGGER_EU_EMBEDDING` | `4` | Hour of day for EU embedding cron. |
| `RUN_STARTUP_PIPELINES_SYNC` | `false` | Block startup until all pipelines finish (useful for debugging). |
| `BM25_K1` | `1.2` | BM25 term-frequency saturation parameter. |
| `ADAPTIVE_CHUNK_THRESHOLD` | `600` | Token count below which documents are embedded as a single chunk. |
| `TOPK_SCORES` | `3` | Top chunk scores averaged per project during result aggregation. |
| `EMBEDDING_CONCURRENCY` | `4` | Maximum parallel embedding tasks per pipeline run. |
| `EU_API_KEY` | — | EU Funding & Tenders Portal API key (`SEDIA` for the public key). |
| `EU_API_URL` | `https://api.tech.ec.europa.eu/search-api/prod/rest/search` | EU search API endpoint. |
| `EU_PAGE_SIZE` | `50` | Records per EU API page. |
| `EU_MAX_PAGES` | `100` | Maximum pages per EU pipeline run. |
| `EU_REQUEST_TIMEOUT_SECONDS` | `30` | HTTP timeout for EU API requests. |
| `EU_PAGE_DELAY_SECONDS` | `0.2` | Delay between EU page fetches. |
| `GERMAN_FUNDING_DATA_URL` | `https://foerderdatenbankdump.fra1.cdn.digitaloceanspaces.com/data/parquet_data.zip` | Source ZIP URL for German data. |

### `streamlit`

Web UI with authentication gating and search pages.

| Property | Value |
|---|---|
| Build context | `.` (repo root), `streamlit/Dockerfile` |
| Container | `sefuse_streamlit` |
| Port | `0.0.0.0:8080:8501` (host port 8080 → container 8501) |
| Networks | `frontend`, `backend` |
| Depends on | `fastapi` (healthy), `postgres` (healthy) |
| Healthcheck | `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"` — 30 s interval, 5 s timeout, 3 retries |
| Restart | on-failure, max 5 attempts |
| Resource limits | 1 GB RAM, 1.0 CPU |
| Security | `no-new-privileges:true`, `read_only: true` |
| Tmpfs | `/tmp`, `/home/appuser` (uid=10001, gid=10001, mode=0700) |

Volume:

| Mount | Mode | Purpose |
|---|---|---|
| `./data/funding_data:/app/data` | read-only | Processed data files for optional offline rendering. |

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `bge-m3` | Embedding model name — must match Ollama and FastAPI. |
| `FASTAPI_URL` | `http://fastapi:8000` | FastAPI base URL. |
| `INTERNAL_API_TOKEN` | — | Shared secret sent as `X-Internal-Token` header. |
| `DB_HOST` | `postgres` | PostgreSQL hostname. |
| `DB_PORT` | `5432` | PostgreSQL port. |
| `DB_NAME` | `$POSTGRES_DB` | Database name. |
| `DB_USER` | `$POSTGRES_USER` | Database user. |
| `DB_PASSWORD` | `$POSTGRES_PASSWORD` | Database password. |
| `DB_CONNECT_TIMEOUT_SECONDS` | `5` | Connection timeout for auth DB operations. |
| `AUTH_ENABLED` | `true` | Set to `false` to disable login requirement. |
| `ADMIN_USERNAME` | — | Username for the bootstrap admin account. |
| `ADMIN_PASSWORD` | — | Password for the bootstrap admin account. |
| `BCRYPT_ROUNDS` | `12` | bcrypt work factor for password hashing. |
| `PASSWORD_MIN_LENGTH` | `8` | Minimum password length enforced on creation/update. |
| `SESSION_TIMEOUT_MINUTES` | `30` | Idle session expiry. |
