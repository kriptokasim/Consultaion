# Backend Test Coverage Policy

This document defines the code coverage requirements, tooling, and execution guides for the Consultaion backend test suite.

---

## Enforced Coverage Thresholds
- **Minimum Enforced Coverage:** **75%** of statements must be covered by unit/integration tests.
- This threshold is defined in the configuration file `apps/api/pytest.ini` via the `--cov-fail-under=75` parameter.
- The CI pipeline will fail automatically if test coverage falls below the 75% limit.

---

## Local Execution Guide

To run the backend test suite locally and generate a coverage report, execute the following commands:

```bash
# Navigate to the API folder
cd apps/api

# Run pytest with default configuration
pytest
```

### Coverage Reports Generated
- **Terminal Summary:** Displays a list of uncovered lines/statements directly in your stdout (via `--cov-report=term-missing`).
- **XML Report:** Saves a detailed XML structure at `apps/api/coverage.xml` (via `--cov-report=xml:coverage.xml`).
- **HTML Report (Optional):** To generate a browsable HTML coverage report, run:
  ```bash
  pytest --cov-report=html
  # Open htmlcov/index.html in your browser
  ```

---

## CI/CD Enforcement & Badging

1. **Gated Checkin:** On every pull request, the CI job `backend-test` runs the tests and generates `coverage.xml`.
2. **Artifact Preservation:** The generated `coverage.xml` is uploaded as a build artifact named `python-coverage` for audibility and audit review.
3. **Badge Generation:** In future iterations, the `python-coverage` artifact can be parsed using a third-party action or custom script to dynamically update a coverage badge on the main repository `README.md`.
