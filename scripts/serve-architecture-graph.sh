#!/usr/bin/env bash
set -euo pipefail

# Configurations
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-8080}"
GRAPHIFY_OUT="$REPO_ROOT/graphify-out"

# Verify that viewer data exists
if [ ! -d "$GRAPHIFY_OUT/code/viewer" ] && [ ! -d "$GRAPHIFY_OUT/repository/viewer" ]; then
  echo "❌ Error: Viewer data or graphs are missing."
  echo "👉 Please run the build script first to generate the profiles:"
  echo "   ./scripts/build-architecture-graph.sh --allow-collision"
  exit 1
fi

echo "🚀 Starting local static server for Graphify Viewers..."
echo "👉 Code Architecture graph:       http://localhost:$PORT/code/viewer/index.html"
echo "👉 Repository Architecture graph: http://localhost:$PORT/repository/viewer/index.html"
echo ""

# Start python static server bound to localhost only
python3 -m http.server "$PORT" --directory "$GRAPHIFY_OUT" --bind 127.0.0.1
