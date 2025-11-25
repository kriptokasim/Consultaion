from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from main import app
from routes.debates import Debate, Score

client = TestClient(app)

def test_export_scores_csv(db_session, reset_global_state):
    session = db_session
    # Create a debate and scores
    import uuid
    debate = Debate(
        id=str(uuid.uuid4()),
        user_id="user-123",
        prompt="Test Prompt",
        title="Test Debate",
        topic="Test Topic",
        persona_a="A",
        persona_b="B",
        model_id="gpt-4",
        provider="openai",
        status="completed",
        created_at=datetime.now(timezone.utc)
    )
    session.add(debate)
    session.commit()
    
    score = Score(
        debate_id=str(debate.id),
        persona="A",
        judge="Judge 1",
        score=8.5,
        rationale="Good",
        created_at=datetime.now(timezone.utc)
    )
    session.add(score)
    session.commit()
    
    # Mock user auth
    from routes.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="user-123")
    
    response = client.get(f"/debates/{debate.id}/scores.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "persona,judge,score" in response.text
    assert "Judge 1" in response.text
    
    app.dependency_overrides = {}
