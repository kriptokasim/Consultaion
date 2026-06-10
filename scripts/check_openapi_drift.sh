#!/usr/bin/env bash
set -eo pipefail

# Find script directory and move to root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Ensure python path includes apps/api
export PYTHONPATH="${PYTHONPATH}:$(pwd)/apps/api"

# Export the latest schema
echo "Exporting current OpenAPI schema..."
python scripts/export_openapi.py

# Check for git diff
echo "Checking for OpenAPI spec drift..."
if ! git diff --exit-code docs/openapi.json; then
    echo "ERROR: OpenAPI spec drift detected. Please run 'python scripts/export_openapi.py' locally and commit the changes to 'docs/openapi.json'."
    exit 1
else
    echo "OpenAPI spec is up to date."
    exit 0
fi
