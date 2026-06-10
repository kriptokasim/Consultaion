import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlmodel import Session, select
from models import Debate
from routes.public_stats import PublicStats


def test_get_public_stats_empty(client: TestClient):
    """
    Test public stats response when the database is empty.
    Should return zero values.
    """
    response = client.get("/public/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["completed_runs"] == 0
    assert data["reports_generated"] == 0
    assert data["active_models"] >= 0
    assert data["avg_divergence_score"] is None


def test_get_public_stats_populated(client: TestClient, db_session: Session):
    """
    Test public stats returns correct aggregate counts from database.
    """
    # Create completed debate with final_meta (report generated)
    debate1 = Debate(
        id="test-run-1",
        prompt="Strategic Pivot",
        status="completed",
        final_meta={"verdict": "proceed"},
    )
    # Create completed debate without final_meta
    debate2 = Debate(
        id="test-run-2",
        prompt="Pricing Check",
        status="completed",
        final_meta=None,
    )
    # Create active (non-completed) debate
    debate3 = Debate(
        id="test-run-3",
        prompt="Running Check",
        status="running",
        final_meta=None,
    )

    db_session.add(debate1)
    db_session.add(debate2)
    db_session.add(debate3)
    db_session.commit()

    # Clear cache by resetting time or restarting the app/router cache
    # But since the test is a clean run, it should fetch fresh database stats
    response = client.get("/public/stats")
    assert response.status_code == 200
    data = response.json()

    # Debate completed: debate1, debate2
    assert data["completed_runs"] == 2
    # Has final_meta and completed: debate1
    assert data["reports_generated"] == 1
