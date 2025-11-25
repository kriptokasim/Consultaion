# Observability & Logging

Consultaion uses structured logging and telemetry to provide visibility into system behavior, performance, and health.

## Logging

### Format
- **Local Development**: Human-readable logs with timestamps and request IDs.
- **Production/Staging**: JSON-structured logs for ingestion by tools like Datadog, CloudWatch, or ELK.

### Configuration
Logging is configured in `apps/api/log_config.py`. The format is automatically selected based on `IS_LOCAL_ENV`.

### Structured Events
Critical lifecycle events are logged with the `log_event` helper, producing structured JSON payloads.

### Debate Lifecycle
- `debate.created`: When a debate is created.
- `debate.started_manually`: When a debate is manually triggered.
- `debate.completed`: When a debate finishes successfully.
  - `duration_seconds`: Total execution time.
  - `tokens_total`: Total tokens consumed.
  - `status`: Final status (e.g., `completed`, `completed_budget`).
- `debate.failed`: When a debate fails.
  - `duration_seconds`: Execution time until failure.
  - `error`: Error message.
  - `error_type`: Exception class name.

### Billing & Limits
- `billing.usage.increment`: When usage is recorded.
- `billing.limit_exceeded`: When a user hits a billing limit.
- `rate_limit.exceeded`: When a request is blocked by rate limiting.

### Infrastructure
- `circuit_breaker.opened`: When a provider circuit breaker opens.

## Correlation Fields
The `log_event` helper automatically injects the following correlation fields when available:
- `request_id`: The unique ID of the HTTP request (via `contextvars`).
- `user_id`: The ID of the authenticated user (passed explicitly).
- `debate_id`: The ID of the debate being processed (passed explicitly).

## Dashboard Caching
To optimize the `list_debates` endpoint, the total count of debates is cached in Redis for **30 seconds**.
- **Cache Key Pattern**: `count:debates:<hash(user_id + status + query)>`
- **TTL**: 30 seconds
- **Invalidation**: Automatic via TTL. No manual invalidation is currently implemented as the count is eventually consistent.

## Telemetry

### Admin Ops
The Admin Ops dashboard (`/admin/ops`) provides real-time visibility into:
- **Provider Health**: Error rates and circuit breaker status for each LLM provider/model.
- **Rate Limits**: Recent 429 events and Redis backend status.
- **System Health**: Database connectivity and SSE backend status.

### Performance
- **Exports**: Heavy export operations (CSV/Markdown) run in a thread pool to avoid blocking the main event loop.
- **Dashboard**: High-traffic counts (e.g., total debates) are cached in Redis (TTL 30s) to reduce database load.

## Troubleshooting

### Missing Logs?
Ensure `LOG_LEVEL` is set correctly (default: INFO).

### Rate Limit Issues?
Check `RATE_LIMIT_BACKEND` setting. If `redis`, ensure `REDIS_URL` is reachable.
View recent 429s in the Admin Ops dashboard.

### Provider Errors?
Check the "Runtime signals" section in Admin Ops. If a circuit is open, it will automatically close after the cooldown period (default: 60s).
