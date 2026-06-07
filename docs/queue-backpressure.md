# Queue Depth & Backpressure Strategy

This document details the background task execution architecture, queue depth limitations, and backpressure mitigation strategy for high-throughput multi-agent debate and evaluation workloads.

---

## 1. Concurrency Models

Consultaion supports two modes of asynchronous execution, configured via the `DEBATE_DISPATCH_MODE` environment variable:

1. **Inline Execution (`inline`)**:
   - Tasks execute directly inside the FastAPI main application thread pool using `anyio` background task helpers.
   - Primarily used in local development and staging environments.
2. **Celery Worker Execution (`celery`)**:
   - Tasks are shipped to a dedicated Celery worker pool using Redis as the transport broker.
   - Designed for production loads to isolate heavy LLM call chains from the web server.

---

## 2. Queue Depth & Concurrency Constraints

To prevent queue runaway and model API starvation, queue depth is constrained through the following strategies:

- **Global Concurrency Limits**: The Celery pool limits concurrent worker processes (e.g. `CELERYD_CONCURRENCY = 16`).
- **Slot Reservation**: Users are checked against active concurrency slots before triggering a run. The `reserve_run_slot` DB helper verifies that a user does not have more than their allowed active concurrent runs (e.g. 2 for Free tier, 5 for Pro tier). If the limit is exceeded, requests are rejected with a `429 Too Many Requests` code.
- **Queue Timeouts**: Jobs in `queued` state have a maximum TTL (e.g. `DEBATE_STALE_QUEUED_SECONDS = 1800`). A background cleanup process automatically cancels and evicts jobs that have been stuck in the queue for too long.

---

## 3. Queue Eviction & API Rate Limiting

When the queue capacity reaches critical thresholds, the following policies handle backpressure:

- **FIFO Queue Strategy**: Jobs are processed in first-in-first-out order by default.
- **Priority-Based Queues**: Critical real-time UI queries land in the `debates_fast` queue, while batch evaluations are routed to `debates_deep`.
- **Preemptive Rate-Limiting**: The system tracks downstream API provider health (using the circuit breaker). If OpenAI or Anthropic is experiencing high error rates or latency, debate starts are immediately blocked, preventing queue pile-ups.

---

## 4. Operator Queue Inspection API (`/admin/queue`)

To give operators visibility into the current queue state, a proposed `/admin/queue` route is documented below.

### Route Specification: `GET /admin/queue`
- **Description**: Returns a snapshot of queued, running, and failed jobs.
- **Access**: Restricted to admin users.
- **Response Format**:
  ```json
  {
    "status": "nominal",
    "queue_depth": {
      "debates_fast": 3,
      "debates_deep": 12
    },
    "active_workers": 4,
    "queued_jobs": [
      {
        "job_id": "job_98765",
        "debate_id": "debate_uuid_1",
        "user_id": "user_uuid_3",
        "status": "queued",
        "enqueued_at": "2026-06-07T15:30:00Z"
      }
    ]
  }
  ```

### Route Specification: `POST /admin/queue/cancel`
- **Description**: Explicitly terminates a queued or stale active run.
- **Payload**:
  ```json
  {
    "job_id": "job_98765",
    "reason": "Operator manually canceled stale execution"
  }
  ```
- **Response**: `200 OK` with status update.
