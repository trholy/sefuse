# Shell Scripts

---

## `ollama/init_models.sh`

Entrypoint for the Ollama container. Starts `ollama serve`, waits for it to become ready, pulls the configured model if absent, then re-execs `ollama serve` as PID 1 so `SIGTERM` from `docker stop` propagates correctly.

### Behavior

1. **Fail-fast on missing `MODEL`** — exits immediately with a clear error if the env var is not set.
2. **Start `ollama serve` in the background** — saves the PID for monitoring.
3. **Wait for readiness** — polls `ollama list` every second up to `OLLAMA_READY_TIMEOUT` (default 60 s). Fails if the timeout is reached or if the `ollama serve` process dies unexpectedly.
4. **Model presence check** — uses a `case` statement to build the correct grep pattern: models without an explicit tag (e.g. `bge-m3`) are matched as `bge-m3:` (any tag); models already specifying a tag (e.g. `llama3:8b`) are matched exactly. This prevents false positives like matching `bge-m3-large` when looking for `bge-m3`.
5. **Pull on first run** — downloads the model only when it is absent. Subsequent container restarts skip the download if the model volume is intact.
6. **Graceful handoff** — stops the background `ollama serve`, waits for it to exit, then `exec`s a fresh `ollama serve` as PID 1.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL` | — | Required. Ollama model name to pull and serve (e.g. `bge-m3`, `llama3:8b`). |
| `OLLAMA_READY_TIMEOUT` | `60` | Maximum seconds to wait for `ollama serve` to accept requests. |

---

## `postgres/check_env.sh`

Entrypoint wrapper for the PostgreSQL container. Validates required environment variables before delegating to the official `docker-entrypoint.sh`.

### Behavior

1. **Missing password check** — exits with a formatted error banner when `POSTGRES_PASSWORD` is empty.
2. **Placeholder password check** — rejects any value starting with `change_me` to prevent accidentally running with an insecure default secret.
3. **Delegation** — `exec`s the official `docker-entrypoint.sh` with all original arguments so the standard PostgreSQL initialization flow runs normally.

The script runs as the `postgres` user (set via `USER postgres` in the Dockerfile). The official entrypoint detects this and skips the root-owned chown/gosu steps, going directly to `initdb`.
