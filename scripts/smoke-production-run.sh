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
# Usage: api_call <path> [expected_status]
# Sets globals: API_CALL_HTTP_CODE, API_CALL_CT_OK, API_CALL_STATUS_OK, API_CALL_BODY_FILE
api_call() {
    local path="$1"
    local expected_status="${2:-200}"
    local url="${API_BASE_URL}${path}"
    
    API_CALL_BODY_FILE=$(mktemp)
    
    API_CALL_HTTP_CODE=$(curl -s -o "$API_CALL_BODY_FILE" -w '%{http_code}' --max-time 30 \
        -H "Cookie: $AUTH_COOKIE" \
        -H "Accept: application/json" \
        "$url")
    
    local content_type
    content_type=$(curl -s -I --max-time 10 -H "Cookie: $AUTH_COOKIE" "$url" | grep -i "content-type" | head -n 1)
    
    API_CALL_STATUS_OK=true
    API_CALL_CT_OK=true
    
    if [ "$API_CALL_HTTP_CODE" -ne "$expected_status" ]; then
        API_CALL_STATUS_OK=false
    fi
    
    if [[ "$content_type" != *"application/json"* ]]; then
        API_CALL_CT_OK=false
    fi
}

echo "=== Production Smoke Test ==="
echo "Target: $API_BASE_URL"
echo "Debate: $TEST_DEBATE_ID"
echo ""

# 1. Health Check
echo "--- 1. GET /healthz ---"
api_call "/healthz" "200"
if [ "$API_CALL_STATUS_OK" = "true" ] && [ "$API_CALL_CT_OK" = "true" ]; then
    if grep -q '"status": "ok"' "$API_CALL_BODY_FILE"; then
        pass "/healthz"
    else
        fail "/healthz (invalid payload)"
    fi
else
    fail "/healthz (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

# 2. Readiness Check
echo "--- 2. GET /readyz ---"
api_call "/readyz" "200"
if [ "$API_CALL_STATUS_OK" = "true" ]; then
    if grep -q '"status": "ready"' "$API_CALL_BODY_FILE"; then
        pass "/readyz"
    else
        fail "/readyz (invalid payload)"
    fi
else
    fail "/readyz (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

# 3. Contracts
echo "--- 3. GET /api/v1/meta/contracts ---"
api_call "/api/v1/meta/contracts" "200"
if [ "$API_CALL_STATUS_OK" = "true" ]; then
    # Use python for safe JSON parsing
    version=$(python3 -c "import sys, json; print(json.load(open(sys.argv[1]))['contracts']['persisted_responses'])" "$API_CALL_BODY_FILE" 2>/dev/null || echo "0")
    if [ "$version" -ge 1 ]; then
        pass "/api/v1/meta/contracts (v$version)"
    else
        fail "/api/v1/meta/contracts (persisted_responses < 1)"
    fi
else
    fail "/api/v1/meta/contracts (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

# 4. Debate Detail
echo "--- 4. GET /debates/$TEST_DEBATE_ID ---"
api_call "/debates/$TEST_DEBATE_ID" "200"
if [ "$API_CALL_STATUS_OK" = "true" ]; then
    # Check ID, status, prompt
    check_id=$(python3 -c "import sys, json; d=json.load(open(sys.argv[1])); print(d.get('id'))" "$API_CALL_BODY_FILE" 2>/dev/null)
    check_status=$(python3 -c "import sys, json; d=json.load(open(sys.argv[1])); print(d.get('status'))" "$API_CALL_BODY_FILE" 2>/dev/null)
    
    if [ "$check_id" = "$TEST_DEBATE_ID" ]; then
        if [[ "$check_status" =~ ^(completed|failed|completed_budget|cancelled|degraded)$ ]]; then
            pass "/debates/$TEST_DEBATE_ID (status: $check_status)"
        else
            fail "/debates/$TEST_DEBATE_ID (non-terminal status: $check_status)"
        fi
    else
        fail "/debates/$TEST_DEBATE_ID (ID mismatch)"
    fi
else
    fail "/debates/$TEST_DEBATE_ID (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

# 5. Responses
echo "--- 5. GET /debates/$TEST_DEBATE_ID/responses ---"
api_call "/debates/$TEST_DEBATE_ID/responses" "200"
if [ "$API_CALL_STATUS_OK" = "true" ]; then
    persisted=$(python3 -c "import sys, json; print(json.load(open(sys.argv[1]))['summary']['persisted'])" "$API_CALL_BODY_FILE" 2>/dev/null || echo "-1")
    if [ "$persisted" -ge 0 ]; then
        # Check content non-empty for at least one if items exist
        if [ "$persisted" -gt 0 ]; then
            content_check=$(python3 -c "
import sys, json
d = json.load(open(sys.argv[1]))
items = d.get('items', [])
has_content = False
for i in items:
    if len(i.get('content', '')) > 0:
        has_content = True
        break
print('ok' if has_content else 'empty')
" "$API_CALL_BODY_FILE" 2>/dev/null || echo "error")
            
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
    fail "/debates/$TEST_DEBATE_ID/responses (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

# 6. Timeline (Optional)
echo "--- 6. GET /debates/$TEST_DEBATE_ID/timeline ---"
api_call "/debates/$TEST_DEBATE_ID/timeline" "200"
if [ "$API_CALL_HTTP_CODE" -eq 200 ]; then
    pass "/debates/$TEST_DEBATE_ID/timeline (available)"
elif [ "$API_CALL_HTTP_CODE" -eq 404 ]; then
    pass "/debates/$TEST_DEBATE_ID/timeline (not found/optional)"
else
    fail "/debates/$TEST_DEBATE_ID/timeline (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

# 7. Events
echo "--- 7. GET /debates/$TEST_DEBATE_ID/events ---"
api_call "/debates/$TEST_DEBATE_ID/events" "200"
if [ "$API_CALL_STATUS_OK" = "true" ]; then
    items=$(python3 -c "import sys, json; print(len(json.load(open(sys.argv[1])).get('items', [])))" "$API_CALL_BODY_FILE" 2>/dev/null || echo "-1")
    if [ "$items" -ge 0 ]; then
        pass "/debates/$TEST_DEBATE_ID/events ($items items)"
    else
        fail "/debates/$TEST_DEBATE_ID/events (invalid payload)"
    fi
else
    fail "/debates/$TEST_DEBATE_ID/events (HTTP $API_CALL_HTTP_CODE)"
fi
rm -f "$API_CALL_BODY_FILE"

echo ""
echo "=== Results: $PASS_COUNT passed, $FAIL_COUNT failed ==="

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi

exit 0
