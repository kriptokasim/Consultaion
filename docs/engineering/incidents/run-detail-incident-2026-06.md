# Run Detail Loading Incident — 2026-06

## Status

Completed Run Detail Incident — Active

## Incident Statement

Production currently shows historical Runs as `completed` in Overview and Recent Runs, but opening a Run leaves the page on skeleton loaders and does not display model responses or history.

## Evidence

| Field | Value |
|-------|-------|
| Problem Run ID | _redacted_ |
| Browser request time | _UTC timestamp_ |
| API SHA | _commit SHA_ |
| Worker SHA | _commit SHA_ |
| Beat SHA | _commit SHA_ |
| GET /debates/{id} status | _HTTP status_ |
| GET /responses status | _HTTP status_ |
| Database response count | _count_ |
| Response roles | _role distribution_ |
| Alembic current | _revision_ |
| Alembic head | _revision_ |

## Root Cause

_To be filled after Render CLI investigation._

## Fix

| Commit | Description |
|--------|-------------|
| _SHA_ | _description_ |

## Post-Deployment Verification

- [ ] All services run the intended SHA
- [ ] Database is at Alembic head
- [ ] Core detail returns 200
- [ ] Responses endpoint returns 200
- [ ] Healthy Run has non-empty responses
- [ ] Terminal empty Run displays explicit empty state
- [ ] Production smoke test passes

## Render CLI Commands Used

```bash
# Service listing
render services list

# Deploy history
render deploys list --service <service-id>

# Logs
render logs --service <service-id> --filter "<debate-id>"

# Shell
render shell --service <service-id>
```

## Known Limitations

_To be filled._
