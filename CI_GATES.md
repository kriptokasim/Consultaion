# PS157 CI Gates

## Backend

```bash
cd apps/api

python -m compileall .
alembic heads

# PS156 fencing
pytest -q -k "lease or checkpoint or fencing" --override-ini="addopts="

# Arena, stream, response, synthesis
pytest -q -k "arena or stream or response or synthesis" --override-ini="addopts="

# Safety, PII, adapter
pytest -q -k "safety or pii or adapter" --override-ini="addopts="

# Full suite
pytest -q --override-ini="addopts="
```

## Frontend

```bash
cd apps/web

npx tsc --noEmit
npm test
npm run build
```

## Generated drift

```bash
python scripts/generate_web_patterns.py
git diff --exit-code apps/web/lib/generatedPatterns.ts
```

## E2E

```bash
npx playwright test --grep "arena|stream|heartbeat|direct-link|run-switch|retry"
```

## Benchmark

```bash
python scripts/ps157_benchmark.py
python scripts/ps157_benchmark.py --verbose
```

## Notes

- Use `--override-ini="addopts="` to bypass the pytest.ini coverage-threshold for CI in test/development mode.
- Production CI should enforce the coverage threshold separately.
- The benchmark harness requires no external services in memory mode.
