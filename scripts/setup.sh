#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

command -v "$PYTHON_BIN" >/dev/null || {
  echo "error: Python 3.11 is required (set PYTHON_BIN to its executable)" >&2
  exit 1
}
command -v node >/dev/null || { echo "error: Node.js 20 is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "error: npm is required" >&2; exit 1; }

python_version="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
node_major="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$python_version" == "3.11" ]] || {
  echo "error: expected Python 3.11, found $python_version" >&2
  exit 1
}
[[ "$node_major" == "20" ]] || {
  echo "error: expected Node.js 20, found $(node --version)" >&2
  exit 1
}

"$PYTHON_BIN" -m venv "$ROOT/apps/api/.venv"
"$ROOT/apps/api/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/apps/api/.venv/bin/python" -m pip install \
  -r "$ROOT/apps/api/requirements.txt" \
  -r "$ROOT/apps/api/requirements-dev.txt"

npm --prefix "$ROOT" ci
npm --prefix "$ROOT/apps/web" ci

printf 'Setup complete.\nAPI Python: %s\nNode: %s\n' \
  "$ROOT/apps/api/.venv/bin/python" "$(node --version)"
