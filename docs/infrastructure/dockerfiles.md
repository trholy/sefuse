# Dockerfiles

Each SeFuSe service has its own Dockerfile. All images run as a non-root user and use pinned base image tags.

---

## FastAPI — `fastapi/Dockerfile`

**Notes:**

- `curl` is installed for the `HEALTHCHECK`; removed from the apt cache layer to keep the image lean.
- `requirements.txt` is copied and installed before source files so Docker layer cache is only invalidated when dependencies change.
- `data_processing/src/` and `shared/` are copied into the image at build time; `data_processing/src` is **also** volume-mounted at runtime (`:ro`) so changes to pipeline code are picked up without a rebuild.
- `appuser` is created with UID 10001 for consistent bind-mount ownership on Linux hosts.
- The container runs with `read_only: true` in Compose; `/tmp` and `/home/appuser` are tmpfs mounts for the tokenizer cache and other transient writes.

---

## Streamlit — `streamlit/Dockerfile`

**Notes:**

- `requirements.txt` is copied first so pip install is cached independently of source changes.
- The `HEALTHCHECK` uses `urllib.request` from the Python standard library because `curl` is not installed in this image.
- `CMD` runs the DB migration (`auth.migrate`) before starting Streamlit. `exec` replaces the shell with the Streamlit process, making it PID 1 so `SIGTERM` from `docker stop` propagates correctly.
- `appuser` UID 10001 matches the FastAPI service for consistent ownership semantics on shared volumes.
- The container runs with `read_only: true` in Compose; `/tmp` and `/home/appuser` are tmpfs mounts.

---

## Ollama — `ollama/Dockerfile`

**Notes:**

- The image extends the official Ollama image with a custom init script.
- `init_models.sh` is the entrypoint; it starts `ollama serve`, waits for readiness, pulls the configured model if absent, then `exec`s `ollama serve` as PID 1.
- The `ollama` user is created idempotently (`id ollama || useradd`) in case the base image does not already include it.
- Model data is stored at `/home/ollama/.ollama` and is persisted via a bind-mount volume (`./ollama/data`).

---

## PostgreSQL — `postgres/Dockerfile`

**Notes:**

- The image extends the official `postgres:16-alpine` image with a startup guard script.
- `check_env.sh` validates that `POSTGRES_PASSWORD` is set and is not a placeholder before delegating to the standard `docker-entrypoint.sh`.
- `USER postgres` runs the entrypoint as the non-root `postgres` user (UID 999). The official postgres entrypoint supports non-root startup: when already running as `postgres` it skips the chown/gosu dance and goes straight to `initdb`.
- On Linux hosts the `./data/postgres` directory must be pre-owned by UID 999: `chown -R 999:999 ./data/postgres`.
