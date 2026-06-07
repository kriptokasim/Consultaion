# Python 3.11 Compatibility & Upgrade Diligence

This document outlines the current Python 3.11 compatibility footprint for Consultaion, catalogs key backend dependencies, and evaluates potential "dependency cliffs" or compatibility issues when planning future migrations (e.g., to Python 3.12+).

---

## Current Runtime Status
* **Python Target:** Python 3.11.x (Active Production Target)
* **Test Suite Status:** Verified green under Python 3.11.9
* **Performance Assessment:** Yields improved performance characteristics (faster startup, better exception tracebacks, and optimized frame execution) compared to older Python runtimes.

---

## Dependency Inventory & Python 3.11 Compatibility

| Package | Version | Python 3.11 Status | Python 3.12 Compatibility Risks |
| --- | --- | --- | --- |
| **FastAPI** | `0.121.0` | ✅ Fully Compatible | None. Active upstream maintenance. |
| **Pydantic** | `2.9.2` | ✅ Fully Compatible | None. First-class support for 3.11/3.12 type hinting. |
| **SQLModel** | `0.0.22` | ✅ Compatible | ⚠️ **Medium Risk:** Relies on older SQLAlchemy and standard library typing. Upgrades may require newer typing syntax updates. |
| **LiteLLM** | `1.61.15` | ✅ Compatible | ⚠️ **Low/Medium Risk:** Heavy dependency tree. Frequent updates require pinning to prevent breaking changes on 3.12 runtime internals. |
| **Celery** | `5.4.0` | ✅ Compatible | ⚠️ **Medium Risk:** Celery uses older async libraries. Moving to Python 3.12+ sometimes shows event-loop deprecation warnings. |
| **psycopg** | `3.2.12` | ✅ Fully Compatible | None. Psycopg 3 has native 3.11/3.12 support. |
| **redis** | `5.2.0` | ✅ Fully Compatible | None. Native async connection pool support. |

---

## Known Python 3.12 Migration Risks ("Dependency Cliffs")

When upgrading Consultaion from Python 3.11 to Python 3.12, the following library-level changes and deprecations pose risks:

### 1. Removal of `distutils`
* **Risk:** Python 3.12 completely removes the `distutils` module.
* **Impact:** Older versions of dependencies or setup scripts that rely on `import distutils` will fail instantly.
* **Remediation:** Ensure all transitive packages are upgraded to versions that do not rely on `distutils` (using `setuptools` instead).

### 2. UTC Datetime Deprecations (`datetime.utcnow()`)
* **Risk:** In Python 3.12, `datetime.utcnow()` and `datetime.utcfromtimestamp()` are formally deprecated and emit runtime deprecation warnings.
* **Impact:** High likelihood of cluttering logs, which can break strict test warning checks.
* **Remediation:** Already resolved in core Consultaion code by using `datetime.now(timezone.utc)` (or the `utcnow()` helper in `models.py` which returns timezone-aware datetimes).

### 3. Starlette & FastAPI Middleware Changes
* **Risk:** Newer ASGI middleware behaviors on Python 3.12 handle event loops slightly differently.
* **Impact:** Celery tasks run eagerly during testing, or custom middleware might experience connection closure edge cases.
* **Remediation:** Pin Starlette to `0.49.1+` and check standard middleware classes for compatibility.

---

## Recommendations & Upgrade Path

1. **Maintain Python 3.11 in CI/CD:** Ensure that GitHub Actions and production Vercel/Docker setups explicitly pin to `python:3.11` to prevent accidental runtime upgrades.
2. **Periodic Dependency Audits:** Run `poetry update` or pip audits quarterly to transition packages to Python 3.12 ready versions.
3. **Upgrade Path:** Before upgrading the production runtime to 3.12, run a staging pipeline with Python 3.12 to verify that all third-party integrations (specifically LiteLLM and SQLModel) compile without warnings.
