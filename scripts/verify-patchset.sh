#!/usr/bin/env bash
# FH125 I-2: Pre-push verification script
# Runs build, test, typecheck, and Alembic head check before pushing.
set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

passed=0
failed=0

run_check() {
    local name="$1"
    shift
    echo -e "${YELLOW}▶ ${name}${NC}"
    if "$@"; then
        echo -e "${GREEN}✓ ${name} passed${NC}"
        passed=$((passed + 1))
    else
        echo -e "${RED}✗ ${name} failed${NC}"
        failed=$((failed + 1))
    fi
    echo
}

echo "═══════════════════════════════════════════════"
echo "  FH125 Pre-Push Verification"
echo "═══════════════════════════════════════════════"
echo

# Frontend checks
if [ -d "apps/web" ]; then
    run_check "Frontend: TypeScript" bash -c "cd apps/web && npx tsc --noEmit"
    run_check "Frontend: Production Build" bash -c "cd apps/web && npm run build"
fi

# Backend checks
if [ -d "apps/api" ]; then
    run_check "Backend: Test Collection" bash -c "cd apps/api && python -m pytest --collect-only -q"
    run_check "Backend: Unit Tests" bash -c "cd apps/api && python -m pytest -x -q"
fi

# Alembic head check (exactly one migration head)
if [ -f "apps/api/alembic.ini" ]; then
    run_check "Alembic: Single Head" bash -c "cd apps/api && python -c \"from alembic.script import ScriptDirectory; from alembic.config import Config; cfg=Config('alembic.ini'); heads=ScriptDirectory.from_config(cfg).get_heads(); assert len(heads) == 1, f'Expected exactly 1 Alembic head, got {len(heads)}: {heads}'\""
fi

# Secret scanner (gitleaks if available)
if command -v gitleaks &>/dev/null; then
    run_check "Secret Scanner" gitleaks detect --no-banner -v
fi

echo "═══════════════════════════════════════════════"
echo -e "  Results: ${GREEN}${passed} passed${NC}, ${RED}${failed} failed${NC}"
echo "═══════════════════════════════════════════════"

if [ $failed -gt 0 ]; then
    echo -e "${RED}Push blocked. Fix failures above.${NC}"
    exit 1
fi

echo -e "${GREEN}All checks passed. Ready to push.${NC}"
