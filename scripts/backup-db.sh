#!/usr/bin/env bash
#
# backup-db.sh — WAL-safe SQLite snapshot for Tasbir.
#
# Tasbir's runtime DB is a single SQLite file (data/tasbir.db) written in WAL
# mode, so a plain `cp` can capture a torn file. This script uses SQLite's
# online backup API (`.backup`) to produce a consistent snapshot while the
# stack is running — no downtime needed.
#
# Usage:
#   scripts/backup-db.sh                      # → data/backups/tasbir-<timestamp>.db
#   scripts/backup-db.sh -o /path/to/dir      # → /path/to/dir/tasbir-<timestamp>.db
#   scripts/backup-db.sh -k 14                # keep only the newest 14 snapshots
#
# Cron example (as the user that owns the repo):
#   0 3 * * *  cd /path/to/tasbir && scripts/backup-db.sh -k 14 >> /var/log/tasbir-backup.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DB_FILE="${TASBIR_DB_FILE:-$REPO_ROOT/backend/data/tasbir.db}"
OUTPUT_DIR=""
KEEP=0

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while getopts "o:k:h" opt; do
  case "$opt" in
    o) OUTPUT_DIR="$OPTARG" ;;
    k) KEEP="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

if [[ ! -f "$DB_FILE" ]]; then
  echo "error: DB not found at $DB_FILE (run the stack once first)" >&2
  exit 1
fi

# sqlite3 is required. On Debian/Ubuntu: apt-get install sqlite3.
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "error: sqlite3 CLI not found — install it (apt-get install sqlite3)" >&2
  exit 1
fi

OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/backend/data/backups}"
mkdir -p "$OUTPUT_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$OUTPUT_DIR/tasbir-$STAMP.db"

echo "[backup] snapshotting $DB_FILE -> $DEST"
# `.backup` uses SQLite's online backup API: safe against a live WAL writer.
sqlite3 "$DB_FILE" ".backup '$DEST'"

SIZE=$(du -h "$DEST" | cut -f1)
echo "[backup] done ($SIZE)"

if [[ "$KEEP" -gt 0 ]]; then
  # Keep the newest $KEEP snapshots, delete the rest (alphabetical == chronological
  # thanks to the timestamped names).
  mapfile -t OLD < <(ls -1 "$OUTPUT_DIR"/tasbir-*.db 2>/dev/null | sort | head -n -"$KEEP" || true)
  for f in "${OLD[@]}"; do
    echo "[backup] pruning $f"
    rm -f "$f"
  done
fi
