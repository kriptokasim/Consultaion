"""Tests for voting access control (private debate protection)."""




class TestVotingAccessControl:
    """Test that voting endpoints enforce debate access control."""

    def test_predict_private_debate_returns_404(self, authenticated_client, db_session):
        """Non-owner cannot predict on a private debate."""
        from models import Debate

        # Create a private debate owned by another user
        debate = Debate(
            id="private-debate-1",
            user_id="other-user-id",
            prompt="Test prompt",
            mode="arena",
            status="running",
            config={"is_public": False},
        )
        db_session.add(debate)
        db_session.commit()

        # Try to predict as the authenticated user
        response = authenticated_client.post(
            "/voting/private-debate-1/predict",
            json={"predicted_winner": "GPT-4o", "confidence_score": 0.7},
        )
        assert response.status_code == 404

    def test_predict_public_debate_allows(self, authenticated_client, db_session):
        """Authenticated user can predict on a public debate."""
        from models import Debate

        debate = Debate(
            id="public-debate-1",
            user_id="other-user-id",
            prompt="Test prompt",
            mode="arena",
            status="running",
            config={"is_public": True},
        )
        db_session.add(debate)
        db_session.commit()

        response = authenticated_client.post(
            "/voting/public-debate-1/predict",
            json={"predicted_winner": "GPT-4o", "confidence_score": 0.7},
        )
        # Should succeed (200) or return business logic error (400), not 404
        assert response.status_code != 404

    def test_reveal_private_debate_returns_404(self, client, db_session):
        """Anonymous cannot reveal private debate prediction data."""
        from models import Debate

        debate = Debate(
            id="private-debate-2",
            user_id="other-user-id",
            prompt="Test prompt",
            mode="arena",
            status="completed",
            config={"is_public": False},
        )
        db_session.add(debate)
        db_session.commit()

        response = client.get("/voting/private-debate-2/reveal")
        assert response.status_code == 404

    def test_predict_nonexistent_debate_returns_404(self, authenticated_client):
        """Predicting on non-existent debate returns 404."""
        response = authenticated_client.post(
            "/voting/nonexistent-debate/predict",
            json={"predicted_winner": "GPT-4o", "confidence_score": 0.7},
        )
        assert response.status_code == 404
