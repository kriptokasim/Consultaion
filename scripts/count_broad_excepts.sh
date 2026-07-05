#!/bin/bash
# Patchset 148 I3: Count broad `except Exception` blocks in the API codebase.
# Use as a CI metric / quality gate to track reduction over time.
#
# Usage:
#   bash scripts/count_broad_excepts.sh
#
# Returns the count and lists file locations.

set -euo pipefail

TARGET="${1:-apps/api}"
echo "=== Broad except count in $TARGET ==="
COUNT=$(grep -rn "except Exception" "$TARGET" --include="*.py" | grep -v "__pycache__" | grep -v ".pyc" | wc -l)
echo "Total: $COUNT"
echo ""
echo "=== Locations ==="
grep -rn "except Exception" "$TARGET" --include="*.py" | grep -v "__pycache__" | grep -v ".pyc" || true
echo ""
echo "Baseline (Patchset 148): Track this number and aim to reduce it."
