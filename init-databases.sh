#!/usr/bin/env bash
#
# init-databases.sh — create additional databases on the automation-db
# PostgreSQL instance at first boot (runs only on empty data dir).
#
# n8n connects to a database named `n8n` (see DB_POSTGRESDB_DATABASE in the
# compose file). Add any other app databases here as needed.
#
# This file is bind-mounted into automation-db. Edit it for your apps and
# re-create the volume (docker compose down -v && up -d) to re-run.

set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE n8n;
EOSQL
