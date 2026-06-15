#!/usr/bin/env bash
# check-alembic-heads.sh — Verify exactly one Alembic migration head exists.
# Exit 0 if single head, exit 1 otherwise.
set -euo pipefail

HEADS_COUNT=$(alembic heads | wc -l)
echo "Alembic heads count: $HEADS_COUNT"

if [ "$HEADS_COUNT" -ne 1 ]; then
  echo "ERROR: Multiple or zero Alembic migration heads detected!"
  echo ""
  echo "Current heads:"
  alembic heads
  echo ""
  echo "Please merge divergent migrations before merging."
  exit 1
fi

echo "OK: Single Alembic migration head confirmed."
