#!/usr/bin/env bash
# Run this once on Linux before the first `docker-compose up --build`.
#
# Every service that writes to a bind mount runs as a fixed non-root UID, but a
# fresh `git clone` leaves the mounted directories owned by the cloning user.
# Linux bind mounts keep the host's ownership — Docker never chowns them — so the
# containers cannot write and die on startup:
#
#   sefuse_postgres | mkdir: can't create directory '/var/lib/postgresql/data/pgdata': Permission denied
#   sefuse_ollama   | Error: open /home/ollama/.ollama/id_ed25519: permission denied
#
# Docker Desktop on macOS and Windows masks this: its filesystem shim presents
# every bind-mounted file as owned by the container user, so no setup is needed
# there and this script exits early.
#
# chmod alone does not help — 755 on a directory owned by another UID still
# denies writes. The owner has to match the UID inside the container.
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Nothing to do on $(uname -s) — Docker Desktop handles bind-mount ownership."
    exit 0
fi

cd "$(dirname "$0")"

# dir:uid:gid — the UID each image's service account actually has.
#   70     postgres in postgres:16-alpine (the Debian image uses 999; this is not it)
#   999    ollama, from `useradd --system` in ollama/Dockerfile
#   10001  appuser in both fastapi/Dockerfile and streamlit/Dockerfile
#   0      qdrant/qdrant runs as root
targets=(
    "./data/postgres:70:70"
    "./ollama/data:999:999"
    "./data/funding_data:10001:10001"
    "./data/qdrant:0:0"
)

if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must chown the data directories, so it needs root:" >&2
    echo "  sudo ./setup.sh" >&2
    exit 1
fi

echo "Preparing SeFuSe data directories..."

for target in "${targets[@]}"; do
    IFS=':' read -r dir uid gid <<< "$target"
    mkdir -p "$dir"
    chown -R "$uid:$gid" "$dir"
    chmod -R u+rwX "$dir"
    echo "  ok  $dir  ->  $uid:$gid"
done

echo ""
echo "Setup complete. Run: docker-compose up --build"
