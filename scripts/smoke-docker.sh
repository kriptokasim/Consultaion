#!/usr/bin/env bash
# smoke-docker.sh — Build and run Docker containers for smoke testing.
# Uses networked topology: web reaches API via service name 'api', not localhost.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.smoke.yml"

cleanup() {
  echo ""
  echo "Cleaning up containers..."
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Docker Smoke Test ==="
echo "Building containers..."
docker compose -f "$COMPOSE_FILE" build

echo "Starting containers..."
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for API health..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
    echo "API is healthy!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API failed to become healthy within 60 seconds"
    docker compose -f "$COMPOSE_FILE" logs api
    exit 1
  fi
  sleep 2
done

echo "Verifying API healthz..."
curl -sf http://localhost:8000/healthz | python3 -m json.tool

echo "Verifying web server..."
curl -sf http://localhost:3000 > /dev/null
echo "Web server OK"

echo "Verifying Alembic single head..."
docker compose -f "$COMPOSE_FILE" exec -T api python -c \
  "from alembic.config import Config; from alembic.script import ScriptDirectory; \
   config = Config('alembic.ini'); script = ScriptDirectory.from_config(config); \
   heads = script.get_heads(); \
   print(f'Heads: {heads}'); \
   assert len(heads) == 1, f'Expected 1 head, got {len(heads)}'"

echo ""
echo "=== All smoke tests passed ==="
