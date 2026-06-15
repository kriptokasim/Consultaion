#!/usr/bin/env bash
# scripts/smoke-docker.sh
# Verifies that both the API and Web docker images build and run successfully,
# passing their respective container health checks.

set -euo pipefail

# Work from the repository root
CDPATH="" cd -- "$(dirname -- "$0")/.."

echo "=== Starting Docker Smoke Test ==="

# Cleanup traps
API_CONTAINER_ID=""
WEB_CONTAINER_ID=""

cleanup() {
  echo "=== Cleaning up smoke test containers ==="
  if [ -n "$WEB_CONTAINER_ID" ]; then
    echo "Stopping web container..."
    docker stop "$WEB_CONTAINER_ID" || true
    docker rm "$WEB_CONTAINER_ID" || true
  fi
  if [ -n "$API_CONTAINER_ID" ]; then
    echo "Stopping api container..."
    docker stop "$API_CONTAINER_ID" || true
    docker rm "$API_CONTAINER_ID" || true
  fi
}
trap cleanup EXIT

# 1. Build API container
echo "Building API Docker image..."
docker build -t consultaion-api:smoke -f apps/api/Dockerfile apps/api

echo "Verifying Alembic migrations inside the API image..."
docker run --rm consultaion-api:smoke sh -c "test -d /app/alembic/versions && alembic heads"

# 2. Build Web container
echo "Building Web Docker image..."
docker build -t consultaion-web:smoke -f apps/web/Dockerfile apps/web

# 3. Start API container
echo "Starting API container..."
# Run with dummy/local settings to prevent dependency blocks
API_CONTAINER_ID=$(docker run -d \
  -p 8000:8000 \
  -e ENV=development \
  -e RATE_LIMIT_BACKEND=memory \
  consultaion-api:smoke)

# 4. Start Web container
echo "Starting Web container..."
WEB_CONTAINER_ID=$(docker run -d \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8000 \
  consultaion-web:smoke)

echo "Waiting for containers to become healthy via HTTP requests..."
MAX_ATTEMPTS=30
ATTEMPT=1
API_HEALTHY=false
WEB_HEALTHY=false

while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
  echo "Attempt $ATTEMPT/$MAX_ATTEMPTS..."
  
  if [ "$API_HEALTHY" = false ]; then
    if curl -fs http://localhost:8000/healthz >/dev/null 2>&1; then
      echo "  API endpoint responded successfully!"
      API_HEALTHY=true
    else
      echo "  API endpoint check failed (will retry)"
    fi
  fi

  if [ "$WEB_HEALTHY" = false ]; then
    if curl -fs http://localhost:3000/api/health >/dev/null 2>&1; then
      echo "  Web endpoint responded successfully!"
      WEB_HEALTHY=true
    else
      echo "  Web endpoint check failed (will retry)"
    fi
  fi

  if [ "$API_HEALTHY" = true ] && [ "$WEB_HEALTHY" = true ]; then
    echo "Both containers are HEALTHY!"
    break
  fi

  sleep 2
  ATTEMPT=$((ATTEMPT + 1))
done

if [ "$API_HEALTHY" = false ] || [ "$WEB_HEALTHY" = false ]; then
  echo "ERROR: Containers did not become healthy within the limit."
  echo "=== API Logs ==="
  docker logs "$API_CONTAINER_ID" || true
  echo "=== Web Logs ==="
  docker logs "$WEB_CONTAINER_ID" || true
  exit 1
fi

echo "=== Smoke Test Passed Successfully ==="
exit 0
