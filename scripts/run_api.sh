#!/usr/bin/env bash
# Start the FastAPI app with the settings from .env (values are never printed).
# Usage: scripts/run_api.sh [extra uvicorn args, e.g. --reload --port 8001]
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "Missing .env (copy .env.example and set ETL_DB_PASSWORD)" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

exec .venv/bin/uvicorn app.main:app "$@"
