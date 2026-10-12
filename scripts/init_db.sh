#!/usr/bin/env bash
# Create (or reset) the school schema and load the fictitious seed data.
# Reads ETL_DB_* settings from .env; the password is never printed.
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

export PGHOST="${ETL_DB_HOST:-localhost}"
export PGPORT="${ETL_DB_PORT:-5432}"
export PGUSER="${ETL_DB_USER:-etl_analyzer}"
export PGDATABASE="${ETL_DB_NAME:-etl_analyzer_db}"
export PGPASSWORD="${ETL_DB_PASSWORD:?ETL_DB_PASSWORD is not set in .env}"

for file in sql/01_schema.sql sql/02_seed.sql; do
    echo "Applying $file"
    psql -v ON_ERROR_STOP=1 -q -f "$file"
done

psql -tA -c "SELECT 'students: ' || count(*) FROM school.students
             UNION ALL
             SELECT 'access_logs: ' || count(*) FROM school.access_logs"
