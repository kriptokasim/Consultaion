#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find_python_311() {
  local candidate requested="${PYTHON_BIN:-}"
  if [[ -n "$requested" ]] && command -v "$requested" >/dev/null 2>&1; then
    candidate="$(command -v "$requested")"
    [[ "$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)" == "3.11" ]] && {
      printf '%s\n' "$candidate"
      return
    }
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    candidate="$(command -v python3.11)"
    [[ "$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)" == "3.11" ]] && {
      printf '%s\n' "$candidate"
      return
    }
  fi
  if command -v pyenv >/dev/null 2>&1; then
    candidate="$(pyenv versions --bare | sed -n '/^3\.11\./p' | sort -V | tail -1)"
    [[ -n "$candidate" ]] && pyenv prefix "$candidate" 2>/dev/null | sed 's|$|/bin/python|'
  fi
}

PYTHON_BIN="$(find_python_311)"
[[ -n "$PYTHON_BIN" && -x "$PYTHON_BIN" ]] || {
  echo "error: Python 3.11 is required but no preinstalled Python 3.11 runtime was found" >&2
  exit 1
}

if [[ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)" != "20" ]]; then
  NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  node20_bin="$(find "$NVM_DIR/versions/node" -mindepth 3 -maxdepth 3 -type f -path '*/v20.*/bin/node' -printf '%h\n' 2>/dev/null | sort -V | tail -1)"
  [[ -n "$node20_bin" ]] || {
    echo "error: Node.js 20 is required but no preinstalled Node.js 20 runtime was found" >&2
    exit 1
  }
  PATH="$node20_bin:$PATH"
  export PATH
fi
command -v npm >/dev/null 2>&1 || { echo "error: npm is required beside Node.js 20" >&2; exit 1; }

printf 'Selected Python: %s\nSelected Node: %s\n' \
  "$("$PYTHON_BIN" --version 2>&1)" "$(node --version)"

"$PYTHON_BIN" -m venv "$ROOT/apps/api/.venv"
"$ROOT/apps/api/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/apps/api/.venv/bin/python" -m pip install \
  -r "$ROOT/apps/api/requirements.txt" \
  -r "$ROOT/apps/api/requirements-dev.txt"

npm --prefix "$ROOT" ci
npm --prefix "$ROOT/apps/web" ci

printf 'Setup complete.\nPython: %s\nNode: %s\n' \
  "$("$ROOT/apps/api/.venv/bin/python" --version 2>&1)" "$(node --version)"
