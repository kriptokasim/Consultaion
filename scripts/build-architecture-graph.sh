#!/usr/bin/env bash
set -euo pipefail

# Configurations
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAPHIFY_OUT="$REPO_ROOT/graphify-out"
VIEWER_SRC="$REPO_ROOT/tools/graph-viewer"

# Default flag values
CLEAN=false
PROFILE="" # build both by default
REUSE_CACHE=true
NO_VIEWER=false
ALLOW_COLLISION=false

# Helper for usage
usage() {
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --clean              Remove all generated data and AST cache"
  echo "  --profile code       Build code architecture profile only"
  echo "  --profile repository Build repository architecture profile only"
  echo "  --reuse-cache        Reuse AST cache (default: true)"
  echo "  --no-viewer          Do not compile/copy viewer assets"
  echo "  --allow-collision    Allow known collision classes (reviewed exception)"
  exit 1
}

# Parse options
while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean) CLEAN=true; shift ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --reuse-cache) REUSE_CACHE=true; shift ;;
    --no-viewer) NO_VIEWER=true; shift ;;
    --allow-collision) ALLOW_COLLISION=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# 1. Identify current repository SHA
GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "no-git-sha")
echo "🔗 Current Repository SHA: $GIT_SHA"

# 2. Print Graphify version
GRAPHIFY_VERSION="0.8.42"
echo "📦 Graphify Version: $GRAPHIFY_VERSION"

# 3. Handle Clean
if [ "$CLEAN" = true ]; then
  echo "🧹 Removing stale generated folders and AST cache..."
  rm -rf "$GRAPHIFY_OUT"
else
  # Safely clean only generated graphs/reports while keeping AST cache if requested
  echo "🧹 Cleaning previous builds (keeping AST cache if present)..."
  rm -rf "$GRAPHIFY_OUT/code"
  rm -rf "$GRAPHIFY_OUT/repository"
  rm -f "$GRAPHIFY_OUT/graph.json"
fi

mkdir -p "$GRAPHIFY_OUT"

# Helper function to build a specific profile
build_profile() {
  local prof="$1"
  local target_dir="$GRAPHIFY_OUT/$prof"
  
  echo "🏗️  Building Profile: $prof..."
  
  # Run validation
  echo "🛡️  Running Symbol Resolution Validation for $prof..."
  local val_flags=""
  if [ "$ALLOW_COLLISION" = true ]; then
    val_flags="--allow-collision"
  fi
  
  # Delegate to validation script
  python3 "$REPO_ROOT/scripts/validate-graphify-symbols.py" --profile "$prof" $val_flags --output "$target_dir/reports/validation-report.json"
  
  # Generate reports and viewer data
  echo "📊 Generating clustering, reports, and viewer data..."
  python3 "$REPO_ROOT/scripts/generate-graph-profile.py" \
    --profile "$prof" \
    --sha "$GIT_SHA" \
    --version "$GRAPHIFY_VERSION" \
    --outdir "$target_dir" \
    $val_flags

  # Copy viewer source
  if [ "$NO_VIEWER" = false ]; then
    echo "🎨 Copying viewer assets to $prof/viewer..."
    mkdir -p "$target_dir/viewer"
    cp "$VIEWER_SRC/index.html" "$target_dir/viewer/"
    cp "$VIEWER_SRC/viewer.js" "$target_dir/viewer/"
    cp "$VIEWER_SRC/viewer.css" "$target_dir/viewer/"
  fi

  # Print metrics from metadata
  local meta_file="$target_dir/reports/build-metadata.json"
  if [ -f "$meta_file" ]; then
    echo "--------------------------------------------------"
    echo "📊 Profile: $prof Summary"
    echo "--------------------------------------------------"
    python3 -c "
import json
with open('$meta_file') as f:
    d = json.load(f)
print(f'   Nodes: {d[\"node_count\"]}')
print(f'   Edges: {d[\"edge_color\" if \"edge_color\" in d else \"edge_count\"]}')
print(f'   Communities: {d[\"community_count\"]}')
print(f'   Ambiguous symbols: {d[\"ambiguous_symbol_count\"]}')
print(f'   Unresolved imports: {d[\"unresolved_import_count\"]}')
print(f'   Validation: {d[\"validation_status\"]}')
"
    echo "--------------------------------------------------"
  fi
}

# Run Builds
if [ -z "$PROFILE" ]; then
  # Build both
  build_profile "code"
  build_profile "repository"
  echo "👉 Final viewing command: ./scripts/serve-architecture-graph.sh"
elif [ "$PROFILE" = "code" ]; then
  build_profile "code"
  echo "👉 Final viewing command: ./scripts/serve-architecture-graph.sh"
elif [ "$PROFILE" = "repository" ]; then
  build_profile "repository"
  echo "👉 Final viewing command: ./scripts/serve-architecture-graph.sh"
else
  echo "❌ Error: Invalid profile '$PROFILE'."
  exit 1
fi

echo "✅ Build completed successfully."
exit 0
