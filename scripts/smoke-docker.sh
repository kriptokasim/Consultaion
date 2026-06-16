#!/usr/bin/env bash
# smoke-docker.sh — Build and run Docker containers for smoke testing.
# Uses PostgreSQL topology with migrate service.
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

echo "Starting PostgreSQL and Redis..."
docker compose -f "$COMPOSE_FILE" up -d postgres redis

echo "Waiting for PostgreSQL and Redis..."
for i in $(seq 1 30); do
  pg_ok=false
  redis_ok=false
  if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U consultaion > /dev/null 2>&1; then
    pg_ok=true
  fi
  if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
    redis_ok=true
  fi
  if $pg_ok && $redis_ok; then
    echo "PostgreSQL and Redis are ready!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Failed to start PostgreSQL or Redis"
    docker compose -f "$COMPOSE_FILE" logs postgres redis
    exit 1
  fi
  sleep 2
done

echo "Running migrations..."
if ! docker compose -f "$COMPOSE_FILE" run --rm migrate; then
  echo "ERROR: Migration failed"
  exit 1
fi
echo "Migration completed successfully"

echo "Starting API..."
docker compose -f "$COMPOSE_FILE" up -d api

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

echo "Verifying API /healthz..."
curl -sf http://localhost:8000/healthz | python3 -m json.tool

echo "Verifying API /readyz..."
if ! curl -sf http://localhost:8000/readyz > /dev/null 2>&1; then
  echo "WARNING: /readyz endpoint not available"
else
  echo "/readyz OK"
fi

echo "Starting Web..."
docker compose -f "$COMPOSE_FILE" up -d web

echo "Waiting for Web health..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo "Web is healthy!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Web failed to start within 60 seconds"
    docker compose -f "$COMPOSE_FILE" logs web
    exit 1
  fi
  sleep 2
done
echo "Web server OK"

echo "Verifying web-to-API proxy..."
if curl -sf http://localhost:3000/api/healthz > /dev/null 2>&1; then
  echo "Web-to-API proxy OK"
else
  echo "WARNING: Web-to-API proxy not responding"
fi

echo "Verifying Alembic single head..."
docker compose -f "$COMPOSE_FILE" exec -T api python -c \
  "from alembic.config import Config; from alembic.script import ScriptDirectory; \
   config = Config('alembic.ini'); script = ScriptDirectory.from_config(config); \
   heads = script.get_heads(); \
   print(f'Heads: {heads}'); \
   assert len(heads) == 1, f'Expected 1 head, got {len(heads)}'"
echo "Alembic head check passed"

echo "Verifying critical database tables exist..."
count="$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U consultaion -d consultaion_smoke -t -c \
  \"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN \
  ('debate', 'debate_continuation', 'billing_reconciliation_runs', 'billing_reconciliation_discrepancies')\" | xargs)"
echo "Critical tables found: $count"
if [ "$count" -lt 4 ]; then
  echo "ERROR: Expected at least 4 critical tables, found $count"
  exit 1
fi

echo ""
echo "=== All smoke tests passed ==="
