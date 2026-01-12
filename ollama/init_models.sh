#!/bin/sh
set -e

if [ -z "$MODEL" ]; then
  echo "MODEL env var not set"
  exit 1
fi

echo "Pulling Ollama model: $MODEL"
ollama pull "$MODEL"
echo "Model downloaded."
