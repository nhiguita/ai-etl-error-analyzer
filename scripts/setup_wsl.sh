#!/usr/bin/env bash
# Installs the system packages and database objects this project needs on Ubuntu 26.04 (WSL2).
# Requires sudo. Run manually: bash scripts/setup_wsl.sh
# Already present (not touched): python3 3.14, PostgreSQL 18 (cluster 18/main on port 5432),
# Ollama with qwen3:4b, NVIDIA driver.
set -euo pipefail

sudo apt-get update

# openjdk-21-jre: Apache Hop 2.19 requires Java 21 (full JRE, not headless, so Hop GUI runs on WSLg).
# unzip: to unpack the Apache Hop client zip (downloaded later without sudo).
sudo apt-get install -y openjdk-21-jre unzip

# PostgreSQL: dedicated login role and database for this project.
# The password is asked interactively and never stored in this script;
# put the same value in your local .env (ETL_DB_PASSWORD), which is not versioned.
read -r -s -p "Password for PostgreSQL role etl_analyzer: " ETL_DB_PASSWORD
echo
sudo -u postgres psql -v ON_ERROR_STOP=1 -v pw="$ETL_DB_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE etl_analyzer LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'etl_analyzer')\gexec
ALTER ROLE etl_analyzer PASSWORD :'pw';
SELECT 'CREATE DATABASE etl_analyzer_db OWNER etl_analyzer'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'etl_analyzer_db')\gexec
SQL

# --- Check (no sudo needed) ---
# java -version                       # should report 21
# PGPASSWORD=... psql -h localhost -U etl_analyzer -d etl_analyzer_db -c 'select current_user'
