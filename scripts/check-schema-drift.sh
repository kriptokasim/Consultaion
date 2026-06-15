#!/usr/bin/env bash
# check-schema-drift.sh — Detect schema drift by comparing Alembic current vs head.
# Exit 0 if in sync, exit 1 if drift detected.
set -euo pipefail

echo "Checking for schema drift..."

# Get current revision from database
CURRENT=$(alembic current 2>/dev/null | head -1 || echo "")
# Get head revision from migration files
HEAD=$(alembic heads 2>/dev/null | head -1 || echo "")

echo "Current revision: ${CURRENT:-<none>}"
echo "Head revision:    ${HEAD:-<none>}"

if [ -z "$HEAD" ]; then
  echo "ERROR: No Alembic migration heads found."
  exit 1
fi

if [ -z "$CURRENT" ]; then
  echo "WARNING: No current revision in database. Database may not be initialized."
  echo "Run 'alembic upgrade head' to apply migrations."
  exit 1
fi

# Compare (first 12 chars for short hash comparison)
CURRENT_SHORT="${CURRENT:0:12}"
HEAD_SHORT="${HEAD:0:12}"

if [ "$CURRENT_SHORT" = "$HEAD_SHORT" ]; then
  echo "OK: Database schema is in sync with migrations."
  exit 0
else
  echo "ERROR: Schema drift detected!"
  echo "  Database is at:  $CURRENT"
  echo "  Migrations at:   $HEAD"
  echo ""
  echo "Run 'alembic upgrade head' to bring database up to date."
  exit 1
fi
