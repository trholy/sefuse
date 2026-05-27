#!/bin/sh
# Starts Ollama, pulls MODEL if absent, then execs ollama serve as PID 1.
set -eu

log() { echo "$(date '+%Y-%m-%dT%H:%M:%S') $*"; }

if [ -z "$MODEL" ]; then
  echo "ERROR: MODEL env var not set" >&2
  exit 1
fi

ollama serve &
OLLAMA_PID=$!

WAIT=0
MAX_WAIT="${OLLAMA_READY_TIMEOUT:-60}"
until ollama list >/dev/null 2>&1; do
  sleep 1
  WAIT=$((WAIT + 1))
  if [ "$WAIT" -ge "$MAX_WAIT" ]; then
    echo "ERROR: ollama serve did not become ready within ${MAX_WAIT}s." >&2
    exit 1
  fi
  if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
    echo "ERROR: ollama serve process died unexpectedly." >&2
    exit 1
  fi
done

# MODEL may already include a tag (e.g. llama3:8b) or not (e.g. bge-m3 → bge-m3:latest).
# Match accordingly so the presence check works in both cases.
case "$MODEL" in
  *:*) MODEL_PATTERN="$MODEL"  ;;
  *)   MODEL_PATTERN="${MODEL}:" ;;
esac

if ollama list | awk 'NR>1 {print $1}' | grep -qF "$MODEL_PATTERN"; then
  log "Model $MODEL already present, skipping pull."
else
  log "Pulling Ollama model: $MODEL"
  if ! ollama pull "$MODEL"; then
    echo "ERROR: Failed to pull model '$MODEL'. Check the model name and network connectivity." >&2
    exit 1
  fi
  log "Model downloaded."
fi

kill "$OLLAMA_PID"
wait "$OLLAMA_PID" 2>/dev/null || true
exec ollama serve
