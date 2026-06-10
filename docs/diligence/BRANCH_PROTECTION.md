# Branch Protection and Governance Policy

To ensure code quality, compliance, and prevent unauthorized modifications to the production environment, Consultaion enforces branch protection rules on the primary repository.

---

## Enforced Branch Protection Rules

The `main` branch is protected with the following rules configured in GitHub:

### 1. Require a Pull Request Before Merging
- All code changes must be submitted via a Pull Request (PR).
- Direct pushing to the `main` branch is strictly disabled for all team members (including administrators).

### 2. Require Status Checks to Pass Before Merging
Before a Pull Request can be merged, all automated checks in our GitHub Actions CI pipeline must report a successful status. The required status checks are:
- `url-scan`: Hardcoded URL Scan.
- `security-scan`: Bandit SAST, dependency auditing, and `gitleaks` scanning (blocking).
- `backend-test`: SQLite test suite coverage.
- `backend-postgres-test`: Postgres 16 integration tests and Alembic single-head verification.
- `openapi-drift-check`: Ensuring generated OpenAPI specs match documentation.
- `frontend-build`: Next.js build validation.
- `e2e-test`: Playwright browser test suite.

### 3. Require Approving Reviews
- At least **1 approving review** from a designated code owner or peer engineer is required.
- Approval must be re-requested if new commits are pushed after the initial review.

### 4. Require Conversation Resolution
- All conversations, code review comments, and threads in the pull request must be marked as resolved before merging.

---

## Remediation & Emergency Bypasses

In extremely rare emergency production incidents where an hotfix bypass is required:
- Only organization administrators can authorize a bypass.
- Any bypass event triggers an audit log in GitHub's organization activity log, which must be documented with an accompanying post-mortem incident report.
