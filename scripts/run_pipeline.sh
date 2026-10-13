#!/usr/bin/env bash
# Run one Apache Hop pipeline headless and keep its console log.
# Usage: scripts/run_pipeline.sh <pipeline_name> [KEY=VALUE ...]
#   ETL_DB_*=... overrides a connection setting for this run (e.g. ETL_DB_PORT=5499);
#   any other KEY=VALUE is passed as a pipeline parameter (e.g. INPUT_FILE=students_sync.csv).
# DB settings come from .env; the password is never printed.
# RUN_LOG_FILE (optional) sets where the log is written; default logs/<pipeline>_<timestamp>.log.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
HOP_HOME="$ROOT/tools/hop"
PROJECT="etl-error-analyzer"
ENVIRONMENT="etl-local"
ENV_FILE="$ROOT/tools/etl-local-env.json"
PIPELINE="${1:?usage: scripts/run_pipeline.sh <pipeline_name> [KEY=VALUE ...]}"
shift
PIPELINE_FILE="$ROOT/hop-pipelines/pipelines/$PIPELINE.hpl"

[[ -f "$PIPELINE_FILE" ]] || { echo "Unknown pipeline: $PIPELINE" >&2; exit 1; }
[[ -f .env ]] || { echo "Missing .env" >&2; exit 1; }

set -a
# shellcheck disable=SC1091
source .env
ETL_DB_HOST="${ETL_DB_HOST:-localhost}"
ETL_DB_PORT="${ETL_DB_PORT:-5432}"
ETL_DB_USER="${ETL_DB_USER:-etl_analyzer}"
ETL_DB_NAME="${ETL_DB_NAME:-etl_analyzer_db}"
set +a

PARAMS=()
for arg in "$@"; do
    [[ "$arg" == *=* ]] || { echo "Expected KEY=VALUE, got: $arg" >&2; exit 1; }
    key="${arg%%=*}"
    if [[ "$key" == ETL_DB_* ]]; then
        export "$arg"
    else
        PARAMS+=(--parameters "$arg")
    fi
done

# Hop does not read OS environment variables, so the DB settings are written to a
# temporary, owner-only environment file that is removed when the run ends.
trap 'rm -f "$ENV_FILE"' EXIT
(
    umask 077
    python3 -I -c '
import json, os, sys
names = ["ETL_DB_HOST", "ETL_DB_PORT", "ETL_DB_USER", "ETL_DB_NAME", "ETL_DB_PASSWORD"]
variables = [{"name": n, "value": os.environ[n], "description": ""} for n in names]
json.dump({"variables": variables}, open(sys.argv[1], "w"))
' "$ENV_FILE"
)

# Register the Hop project and environment once (stored in tools/hop/config, not versioned).
if ! grep -q "\"$PROJECT\"" "$HOP_HOME/config/hop-config.json"; then
    "$HOP_HOME/hop-conf.sh" --project-create --project "$PROJECT" \
        --project-home "$ROOT/hop-pipelines" --project-config-file project-config.json >/dev/null
fi
if ! grep -q "\"$ENVIRONMENT\"" "$HOP_HOME/config/hop-config.json"; then
    "$HOP_HOME/hop-conf.sh" --environment-create --environment "$ENVIRONMENT" \
        --environment-project "$PROJECT" --environment-purpose Development \
        --environment-config-files "$ENV_FILE" >/dev/null
fi

LOG_FILE="${RUN_LOG_FILE:-logs/${PIPELINE}_$(date +%Y%m%d_%H%M%S).log}"
mkdir -p "$(dirname "$LOG_FILE")"

set +e
"$HOP_HOME/hop-run.sh" --environment "$ENVIRONMENT" --file "$PIPELINE_FILE" \
    --runconfig local --level BASIC "${PARAMS[@]}" > "$LOG_FILE" 2>&1
STATUS=$?
set -e

echo "Pipeline $PIPELINE finished with exit code $STATUS; log: $LOG_FILE"
exit "$STATUS"
