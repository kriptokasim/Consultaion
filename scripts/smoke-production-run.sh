#!/usr/bin/env bash
# smoke-production-run.sh — Authenticated Production Smoke Test (FH123)
# Checks core API health and debate data integrity.
#
# Inputs (environment variables):
#   API_BASE_URL    (default: http://localhost:8000)
#   TEST_DEBATE_ID  (required)
#   AUTH_COOKIE     (required)

set -euo pipefail

# Defaults
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TEST_DEBATE_ID="${TEST_DEBATE_ID:-}"
AUTH_COOKIE="${AUTH_COOKIE:-}"

# Validation
if [ -z "$TEST_DEBATE_ID" ]; then
    echo "ERROR: TEST_DEBATE_ID environment variable is required."
    exit 1
fi

if [ -z "$AUTH_COOKIE" ]; then
    echo "ERROR: AUTH_COOKIE environment variable is required."
    exit 1
fi

PASS_COUNT=0
FAIL_COUNT=0

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "[PASS] $1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "[FAIL] $1"
}

# Helper to make authenticated curl requests
# Usage: api_call <path> [expected_status] [expected_field]
api_call() {
    local path="$1"
    local expected_status="${2:-200}"
    local url="${API_BASE_URL}${path}"
    
    local tmp_body
    tmp_body=$(mktemp)
    
    local http_code
    http_code=$(curl -s -o "$tmp_body" -w '%{http_code}' \
        -H "Cookie: $AUTH_COOKIE" \
        -H "Accept: application/json" \
        "$url")
    
    local content_type
    content_type=$(curl -s -I -H "Cookie: $AUTH_COOKIE" "$url" | grep -i "content-type" | head -n 1)
    
    local status_ok=true
    local ct_ok=true
    
    if [ "$http_code" -ne "$expected_status" ]; then
        status_ok=false
    fi
    
    if [[ "$content_type" != *"application/json"* ]]; then
        ct_ok=false
    fi
    
    # Output results for caller processing
    echo "$http_code|$ct_ok|$status_ok|$(cat "$tmp_body")"
    rm -f "$tmp_body"
}

echo "=== Production Smoke Test ==="
echo "Target: $API_BASE_URL"
echo "Debate: $TEST_DEBATE_ID"
echo ""

# 1. Health Check
echo "--- 1. GET /healthz ---"
result=$(api_call "/healthz" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
ct_ok=$(echo "$result" | cut -d'|' -f2)
status_ok=$(echo "$result" | cut -d'|' -f3)
body=$(echo "$result" | cut -d'|' -f4-)

if [ "$status_ok" = "true" ] && [ "$ct_ok" = "true" ]; then
    if echo "$body" | grep -q '"status": "ok"'; then
        pass "/healthz"
    else
        fail "/healthz (invalid payload)"
    fi
else
    fail "/healthz (HTTP $http_code)"
fi

# 2. Readiness Check
echo "--- 2. GET /readyz ---"
result=$(api_call "/readyz" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
status_ok=$(echo "$result" | cut -d'|' -f3)
body=$(echo "$result" | cut -d'|' -f4-)

if [ "$status_ok" = "true" ]; then
    if echo "$body" | grep -q '"status": "ready"'; then
        pass "/readyz"
    else
        fail "/readyz (invalid payload)"
    fi
else
    fail "/readyz (HTTP $http_code)"
fi

# 3. Contracts
echo "--- 3. GET /api/v1/meta/contracts ---"
result=$(api_call "/api/v1/meta/contracts" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
status_ok=$(echo "$result" | cut -d'|' -f3)
body=$(echo "$result" | cut -d'|' -f4-)

if [ "$status_ok" = "true" ]; then
    # Use python for safe JSON parsing
    version=$(echo "$body" | python3 -c "import sys, json; print(json.load(sys.stdin)['contracts']['persisted_responses'])" 2>/dev/null || echo "0")
    if [ "$version" -ge 1 ]; then
        pass "/api/v1/meta/contracts (v$version)"
    else
        fail "/api/v1/meta/contracts (persisted_responses < 1)"
    fi
else
    fail "/api/v1/meta/contracts (HTTP $http_code)"
fi

# 4. Debate Detail
echo "--- 4. GET /debates/$TEST_DEBATE_ID ---"
result=$(api_call "/debates/$TEST_DEBATE_ID" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
status_ok=$(echo "$result" | cut -d'|' -f3)
body=$(echo "$result" | cut -d'|' -f4-)

if [ "$status_ok" = "true" ]; then
    # Check ID, status, prompt
    check_id=$(echo "$body" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id'))" 2>/dev/null)
    check_status=$(echo "$body" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status'))" 2>/dev/null)
    
    if [ "$check_id" = "$TEST_DEBATE_ID" ]; then
        if [[ "$check_status" =~ ^(completed|failed|completed_budget)$ ]]; then
            pass "/debates/$TEST_DEBATE_ID (status: $check_status)"
        else
            fail "/debates/$TEST_DEBATE_ID (non-terminal status: $check_status)"
        fi
    else
        fail "/debates/$TEST_DEBATE_ID (ID mismatch)"
    fi
else
    fail "/debates/$TEST_DEBATE_ID (HTTP $http_code)"
fi

# 5. Responses
echo "--- 5. GET /debates/$TEST_DEBATE_ID/responses ---"
result=$(api_call "/debates/$TEST_DEBATE_ID/responses" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
status_ok=$(echo "$result" | cut -d'|' -f3)
body=$(echo "$result" | cut -d'|' -f4-)

if [ "$status_ok" = "true" ]; then
    persisted=$(echo "$body" | python3 -c "import sys, json; print(json.load(sys.stdin)['summary']['persisted'])" 2>/dev/null || echo "-1")
    if [ "$persisted" -ge 0 ]; then
        # Check content non-empty for at least one if items exist
        if [ "$persisted" -gt 0 ]; then
            content_check=$(echo "$body" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', [])
has_content = False
for i in items:
    if len(i.get('content', '')) > 0:
        has_content = True
        break
print('ok' if has_content else 'empty')
" 2>/dev/null || echo "error")
            
            if [ "$content_check" = "ok" ]; then
                pass "/debates/$TEST_DEBATE_ID/responses ($persisted items)"
            else
                fail "/debates/$TEST_DEBATE_ID/responses (empty content)"
            fi
        else
            pass "/debates/$TEST_DEBATE_ID/responses ($persisted items)"
        fi
    else
        fail "/debates/$TEST_DEBATE_ID/responses (invalid summary)"
    fi
else
    fail "/debates/$TEST_DEBATE_ID/responses (HTTP $http_code)"
fi

# 6. Timeline (Optional)
echo "--- 6. GET /debates/$TEST_DEBATE_ID/timeline ---"
result=$(api_call "/debates/$TEST_DEBATE_ID/timeline" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
if [ "$http_code" -eq 200 ]; then
    pass "/debates/$TEST_DEBATE_ID/timeline (available)"
elif [ "$http_code" -eq 404 ]; then
    pass "/debates/$TEST_DEBATE_ID/timeline (not found/optional)"
else
    fail "/debates/$TEST_DEBATE_ID/timeline (HTTP $http_code)"
fi

# 7. Events
echo "--- 7. GET /debates/$TEST_DEBATE_ID/events ---"
result=$(api_call "/debates/$TEST_DEBATE_ID/events" "200")
http_code=$(echo "$result" | cut -d'|' -f1)
status_ok=$(echo "$result" | cut -d'|' -f3)
body=$(echo "$result" | cut -d'|' -f4-)

if [ "$status_ok" = "true" ]; then
    items=$(echo "$body" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('items', [])))" 2>/dev/null || echo "-1")
    if [ "$items" -ge 0 ]; then
        pass "/debates/$TEST_DEBATE_ID/events ($items items)"
    else
        fail "/debates/$TEST_DEBATE_ID/events (invalid payload)"
    fi
else
    fail "/debates/$TEST_DEBATE_ID/events (HTTP $http_code)"
fi

echo ""
echo "=== Results: $PASS_COUNT passed, $FAIL_COUNT failed ==="

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi

exit 0
