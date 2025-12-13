# Supabase + Render Ops Runbook

## Overview

This project uses Supabase as the PostgreSQL provider and Render as the compute platform.
We use a **split connection strategy** to support both transactional pooling (PgBouncer) for the runtime and direct connections for migrations.

## Database Connections

### 1. Runtime (`DATABASE_URL`)

* **Purpose:** Application read/write traffic.
* **Port:** `6543` (Supabase Transaction Pooler / PgBouncer).
* **Format:** `postgresql+psycopg://<user>:<password>@<pooler-host>:6543/postgres?sslmode=require`
* **Code Behavior:**
  * Application disables prepared statements (`prepare_threshold=0`) when connecting to this port to avoid PgBouncer incompatibility.

### 2. Migrations (`DATABASE_URL_MIGRATIONS`)

* **Purpose:** Running Alembic migrations (`alembic upgrade head`).
* **Port:** `5432` (Direct PostgreSQL Connection).
* **Format:** `postgresql+psycopg://<user>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require`
* **Code Behavior:**
  * `alembic/env.py` prefers this URL if set.
  * Essential because transactional poolers cannot handle some DDL statements (like large locking migrations) reliably, and direct connection supports all DDL.
* **Note:** If direct IPv6 host is unreachable from Render, we can fall back to the pooler URL (port 6543) for migrations too (patchset 68.1 enabled this), but Direct is preferred if network allows.

## Render Configuration

### Environment Variables

| Variable | Value Pattern | Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | `...:6543...` | Supabase Pooler |
| `DATABASE_URL_MIGRATIONS` | `...:5432...` | Supabase Direct (if reachable) |
| `SSE_BACKEND` | `memory` or `redis` | Use `memory` for single-instance |
| `REDIS_URL` | `redis://...` | Required if `SSE_BACKEND=redis` |
| `APP_VERSION` | `0.2.0` | Exposed in `/healthz` |

### Deploy Command

```bash
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers
```

## Readiness Checks (`/readyz`)

The `/readyz` endpoint returns **200 OK** only when:

1. **DB Ping:** Application can execute `SELECT 1`.
2. **Migrations:** Current DB revision matches `alembic head`.
3. **SSE:** SSE Backend is pingable (Redis or Memory).

If any check fails (e.g., pending migrations), it returns **503 Service Unavailable**.

## Troubleshooting

### 500 Error on Login

**Cause:** Using Supabase Pooler (6543) without disabling prepared statements.
**Fix:** Ensure code patchset 68 is deployed.

### Network is unreachable (IPv6)

**Cause:** Render cannot reach `db.<ref>.supabase.co` (often IPv6 only).
**Fix:** Unset `DATABASE_URL_MIGRATIONS` to force Alembic to use the Pooler URL (`DATABASE_URL`), which is IPv4 compatible.

### "/readyz" returns 503

**Cause:** Migrations likely failed or haven't run.
**Fix:** Check build logs for `alembic upgrade head` output. Run migrations manually if needed.
