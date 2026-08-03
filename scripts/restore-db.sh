#!/usr/bin/env bash
#
# restore-db.sh — restore a Tasbir SQLite snapshot.
#
# Safety: before restoring, the current DB is automatically backed up to
# data/backups/pre-restore-<timestamp>.db so a restore is never destructive.
#
# IMPORTANT: restore while the stack is STOPPED (docker compose stop api worker
# beat) so no process writes to the DB mid-restore.
#
# Usage:
#   scripts/restore-db.sh data/backups/tasbir-20260803-030000.db

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DB_FILE="${TASBIR_DB_FILE:-$REPO_ROOT/backend/data/tasbir.db}"
BACKUP_DIR="$REPO_ROOT/backend/data/backups"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <backup.db>" >&2
  echo "  e.g. $0 data/backups/tasbir-20260803-030000.db" >&2
  exit 1
fi

SRC="${1#./}"
if [[ "$SRC" != /* ]]; then
  SRC="$REPO_ROOT/$SRC"
fi

if [[ ! -f "$SRC" ]]; then
  echo "error: backup not found: $SRC" >&2
  exit 1
fi

# Sanity: the source must be a valid SQLite file.
if ! sqlite3 "$SRC" "PRAGMA quick_check;" >/dev/null 2>&1; then
  echo "error: '$SRC' does not look like a valid SQLite database" >&2
  exit 1
fi

if [[ -f "$DB_FILE" ]]; then
  mkdir -p "$BACKUP_DIR"
  STAMP="$(date +%Y%m%d-%H%M%S)"
  PRE="$BACKUP_DIR/pre-restore-$STAMP.db"
  echo "[restore] backing up current DB -> $PRE"
  sqlite3 "$DB_FILE" ".backup '$PRE'"
fi

echo "[restore] restoring $SRC -> $DB_FILE"
mkdir -p "$(dirname "$DB_FILE")"
# sqlite3 requires the destination file to exist for .restore.
: > "$DB_FILE"
sqlite3 "$DB_FILE" ".restore '$SRC'"

# Tidy up the WAL/shm sidecars left over from the pre-restore writer.
rm -f "$DB_FILE-wal" "$DB_FILE-shm"

echo "[restore] done. Restart the stack: docker compose up -d"
