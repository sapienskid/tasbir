#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

echo "Running database migrations..."
alembic upgrade head

echo "Seeding default data..."
python ../scripts/seed.py

echo "Done."
