#!/usr/bin/env bash
set -euo pipefail

echo "Consultaion API — production startup"
echo "Running safe migration..."

python scripts/migrate_database.py

echo "Migration complete. Starting API server..."

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
