#!/usr/bin/env bash
set -euo pipefail

echo "Consultaion API — production startup"
echo "Verifying database schema (migrations should be run via Release Command)..."

python scripts/migrate_database.py --check || {
    echo "FATAL: Database schema is not up to date. Release Command failed or has not run."
    exit 1
}

echo "Schema verification passed. Starting API server..."

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
