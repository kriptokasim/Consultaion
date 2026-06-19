"""Route inventory snapshot test.

Captures and validates the route inventory to detect unintended changes.
Run this test to generate a baseline, then re-run to verify no drift.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app

INVENTORY_FILE = Path(__file__).parent.parent.parent.parent / "docs" / "audits" / "route-inventory.json"


def _extract_routes(client: TestClient) -> list[dict]:
    """Extract route inventory from OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()

    routes = []
    for path, methods in openapi.get("paths", {}).items():
        for method, spec in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                routes.append({
                    "path": path,
                    "method": method.upper(),
                    "operation_id": spec.get("operationId", ""),
                    "tags": spec.get("tags", []),
                    "summary": spec.get("summary", ""),
                })

    return sorted(routes, key=lambda r: (r["path"], r["method"]))


def test_route_inventory_snapshot():
    """Verify route inventory matches baseline."""
    client = TestClient(app, raise_server_exceptions=False)
    current = _extract_routes(client)

    if INVENTORY_FILE.exists():
        baseline = json.loads(INVENTORY_FILE.read_text())
        assert current == baseline, (
            f"Route inventory changed. {len(current)} routes now vs {len(baseline)} baseline. "
            f"Run `pytest tests/test_route_inventory.py --update-inventory` to update."
        )
    else:
        pytest.skip("No baseline inventory file. Run with --update-inventory to create one.")


def test_no_duplicate_route_registration():
    """Verify no duplicate route+method combinations."""
    client = TestClient(app, raise_server_exceptions=False)
    routes = _extract_routes(client)

    seen = set()
    duplicates = []
    for r in routes:
        key = (r["path"], r["method"])
        if key in seen:
            duplicates.append(key)
        seen.add(key)

    assert not duplicates, f"Duplicate routes found: {duplicates}"


def test_all_routes_have_operation_ids():
    """Verify all routes have operation IDs for client generation."""
    client = TestClient(app, raise_server_exceptions=False)
    routes = _extract_routes(client)

    missing = [r for r in routes if not r["operation_id"]]
    assert not missing, f"Routes without operation_id: {[r['path'] for r in missing]}"


def test_api_v1_prefix_preserved():
    """Verify /api/v1 prefix routes exist."""
    client = TestClient(app, raise_server_exceptions=False)
    routes = _extract_routes(client)

    v1_routes = [r for r in routes if r["path"].startswith("/api/v1")]
    assert len(v1_routes) > 0, "No /api/v1 routes found"


def test_openapi_matches_baseline():
    """Verify OpenAPI spec hasn't changed unexpectedly."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/openapi.json")
    openapi = response.json()

    openapi_file = INVENTORY_FILE.parent / "openapi-baseline.json"
    if openapi_file.exists():
        baseline = json.loads(openapi_file.read_text())
        assert openapi == baseline, "OpenAPI spec changed"
    else:
        pytest.skip("No OpenAPI baseline file")
