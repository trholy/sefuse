#!/bin/sh
set -e

if [ -z "$MODEL" ]; then
  echo "MODEL env var not set"
  exit 1
fi

if ollama list | grep -q "$MODEL"; then
  echo "Model $MODEL already present, skipping pull."
else
  echo "Pulling Ollama model: $MODEL"
  ollama pull "$MODEL"
  echo "Model downloaded."
fi
