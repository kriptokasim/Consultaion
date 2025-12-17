# SSE Backend Operations Guide

Server-Sent Events (SSE) enables real-time streaming of debate progress to clients.

## Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `SSE_BACKEND` | `memory`, `redis` | `memory` | Backend type for SSE pub/sub |
| `REDIS_URL` | URL | - | Redis connection URL |
| `SSE_REDIS_URL` | URL | - | Dedicated Redis URL for SSE (optional) |
| `SSE_REDIS_STRICT` | `0`, `1` | auto | Strict mode: fail if Redis configured but unavailable |
| `SSE_CHANNEL_TTL_SECONDS` | int | `900` | Channel expiry time |
| `SSE_MEMORY_MAX_QUEUE_SIZE` | int | `1000` | Max events per channel (memory backend) |
| `SSE_MEMORY_IDLE_TIMEOUT_SECONDS` | int | `3600` | Max idle time for subscriptions |

## Deployment Configurations

### Single Instance (Memory Backend)

```bash
SSE_BACKEND=memory
```

Memory backend is simpler but events won't be shared across multiple workers or instances.

### Multi-Instance (Redis Backend)

```bash
SSE_BACKEND=redis
REDIS_URL=redis://user:password@redis-host:6379/0
SSE_REDIS_STRICT=1
```

Redis enables SSE events shared across all workers/instances.

## Strict Mode

Controls behavior when `SSE_BACKEND=redis` but Redis is unavailable.

| Environment | Default | Invalid Redis URL |
|-------------|---------|-------------------|
| Production | Strict (`1`) | **Startup fails** |
| Local/Dev | Non-strict (`0`) | Falls back to memory |

Override with `SSE_REDIS_STRICT=0` (allow fallback) or `SSE_REDIS_STRICT=1` (always fail).

## Health Checks

```bash
curl http://localhost:8000/readyz | jq '.details.sse'
```

## Troubleshooting

### "SSE_BACKEND=redis but URL is invalid"

Set valid `REDIS_URL` or switch to `SSE_BACKEND=memory`.

### Events not delivered to all clients

Using memory backend with multiple workers. Switch to Redis backend.

### Subscription timeout

Expected behavior (default 1 hour idle timeout). Clients should reconnect.

## Render/Vercel Setup

**Single Instance:**

```bash
SSE_BACKEND=memory
```

**Multi-Instance:**

```bash
SSE_BACKEND=redis
REDIS_URL=<your-redis-url>
SSE_REDIS_STRICT=1
```
