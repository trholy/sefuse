#!/bin/sh
set -e

if [ -z "$POSTGRES_PASSWORD" ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║  STARTUP FAILED: POSTGRES_PASSWORD is not set                    ║"
    echo "║                                                                  ║"
    echo "║  Before running docker-compose, set up your .env file:           ║"
    echo "║    1. cp .env.example .env                                       ║"
    echo "║    2. Replace all change_me_* values with real secrets           ║"
    echo "║                                                                  ║"
    echo "║  See README.md → Security Notes for details.                     ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    exit 1
fi

case "$POSTGRES_PASSWORD" in
    change_me*)
        echo ""
        echo "╔══════════════════════════════════════════════════════════════════╗"
        echo "║  STARTUP FAILED: POSTGRES_PASSWORD still uses a placeholder      ║"
        echo "║                                                                  ║"
        echo "║  Edit .env and replace the change_me_* value with a real secret. ║"
        echo "║  See README.md → Security Notes for details.                     ║"
        echo "╚══════════════════════════════════════════════════════════════════╝"
        exit 1
        ;;
esac

exec /usr/local/bin/docker-entrypoint.sh "$@"
