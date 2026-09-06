#!/usr/bin/env bash
set -euo pipefail

echo "Consultaion API — production startup"
echo "Verifying database schema (migrations should be run via Release Command)..."

python scripts/migrate_database.py --check || {
    echo "FATAL: Database schema is not up to date. Release Command failed or has not run."
    exit 1
}

echo "Schema verification passed. Starting API server..."

# Which upstream hops may set X-Forwarded-For. With "*", uvicorn trusts the
# leftmost — entirely client-supplied — hop and rewrites scope["client"] to it,
# which makes every per-IP rate limit (login, register, debate creation, the
# LLM action guard) trivially bypassable with a spoofed header. Set this to the
# CIDR of your actual edge proxy, and keep TRUSTED_PROXY_CIDRS in sync with it.
APP_ENVIRONMENT="${ENV:-${APP_ENV:-production}}"
if [ -z "${FORWARDED_ALLOW_IPS:-}" ]; then
    case "${APP_ENVIRONMENT}" in
        local|development|test)
            FORWARDED_ALLOW_IPS="127.0.0.1"
            ;;
        *)
            echo "FATAL: FORWARDED_ALLOW_IPS is not set."
            echo "  Set it to your platform's ingress CIDR (e.g. 10.0.0.0/8), or to the"
            echo "  literal edge IP. Do not set it to '*' — that trusts a client-supplied"
            echo "  X-Forwarded-For and disables every per-IP rate limit."
            exit 1
            ;;
    esac
fi

if [ "${FORWARDED_ALLOW_IPS}" = "*" ]; then
    echo "WARNING: FORWARDED_ALLOW_IPS='*' trusts a client-supplied X-Forwarded-For."
    echo "         Per-IP rate limiting is not enforceable in this configuration."
fi

# Without an explicit budget uvicorn waits indefinitely for open connections on
# SIGTERM. SSE streams never close on their own, so the process hangs until the
# platform SIGKILLs it, killing in-flight runs mid-write.
GRACEFUL_TIMEOUT="${GRACEFUL_SHUTDOWN_SECONDS:-25}"

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}" \
  --timeout-graceful-shutdown "${GRACEFUL_TIMEOUT}"
