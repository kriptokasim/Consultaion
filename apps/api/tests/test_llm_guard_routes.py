"""Tests for LLM guard wiring in route handlers.

Verifies that require_llm_action_allowed is called by each expensive route,
and that guard denial prevents DB side effects.
"""

from unittest.mock import patch


def _get_user_id(client, db_session):
    """Get the user ID from the authenticated client."""
    from auth import COOKIE_NAME, decode_access_token
    token = client.cookies.get(COOKIE_NAME)
    payload = decode_access_token(token)
    return payload.get("sub") or payload.get("user_id")


class TestGuardWiring:
    """Verify each route calls require_llm_action_allowed."""

    @patch("routes.oracle.require_llm_action_allowed")
    def test_oracle_create_calls_guard(self, mock_guard, authenticated_client, db_session):
        """POST /oracle calls guard with oracle_session action."""
        response = authenticated_client.post(
            "/oracle",
            json={"prompt": "Test oracle prompt for analysis"},
        )
        assert response.status_code == 200
        mock_guard.assert_called_once()
        call_kwargs = mock_guard.call_args[1]
        assert call_kwargs["action"] == "oracle_session"

    @patch("routes.oracle.require_llm_action_allowed")
    def test_oracle_fork_calls_guard(self, mock_guard, authenticated_client, db_session):
        """POST /oracle/{id}/fork calls guard with oracle_fork action."""
        # Create oracle session first
        create_resp = authenticated_client.post(
            "/oracle",
            json={"prompt": "Test oracle prompt for fork"},
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]
        root_branch_id = create_resp.json()["root_branch_id"]

        mock_guard.reset_mock()

        response = authenticated_client.post(
            f"/oracle/{session_id}/fork",
            json={
                "parent_branch_id": root_branch_id,
                "fork_node_id": "node-1",
                "assumption_text": "What if the opposite were true?",
            },
        )
        assert response.status_code == 200
        mock_guard.assert_called_once()
        call_kwargs = mock_guard.call_args[1]
        assert call_kwargs["action"] == "oracle_fork"

    @patch("routes.redteam.require_llm_action_allowed")
    def test_redteam_create_calls_guard(self, mock_guard, authenticated_client, db_session):
        """POST /redteam calls guard with redteam_session action."""
        response = authenticated_client.post(
            "/redteam",
            json={"proposal_text": "This is a test proposal for red team analysis", "lenses": ["security"]},
        )
        assert response.status_code == 200
        mock_guard.assert_called_once()
        call_kwargs = mock_guard.call_args[1]
        assert call_kwargs["action"] == "redteam_session"

    @patch("routes.challenge.require_llm_action_allowed")
    def test_challenge_round_calls_guard(self, mock_guard, authenticated_client, db_session):
        """POST /challenge/{id}/round calls guard with challenge_round action."""
        from models import ChallengeSession, Debate

        user_id = _get_user_id(authenticated_client, db_session)

        # Create a completed debate
        debate = Debate(
            id="test-debate-guard",
            user_id=user_id,
            prompt="Test debate prompt",
            mode="debate",
            status="completed",
        )
        db_session.add(debate)
        db_session.commit()

        # Create challenge session
        challenge = ChallengeSession(
            id="test-challenge-guard",
            user_id=user_id,
            debate_id="test-debate-guard",
        )
        db_session.add(challenge)
        db_session.commit()

        mock_guard.reset_mock()

        response = authenticated_client.post(
            "/challenge/test-challenge-guard/round",
            json={"pushback_text": "I disagree with this synthesis"},
        )
        # May fail at LLM call stage, but guard should have been called first
        assert response.status_code in (200, 500)
        mock_guard.assert_called_once()
        call_kwargs = mock_guard.call_args[1]
        assert call_kwargs["action"] == "challenge_round"
        assert call_kwargs["debate_id"] == "test-debate-guard"

    @patch("routes.voting.require_llm_action_allowed")
    def test_voting_predict_calls_guard(self, mock_guard, authenticated_client, db_session):
        """POST /voting/{id}/predict calls guard with voting_prediction action."""
        from models import Debate

        user_id = _get_user_id(authenticated_client, db_session)

        debate = Debate(
            id="test-vote-guard",
            user_id=user_id,
            prompt="Test voting prompt",
            mode="arena",
            status="running",
        )
        db_session.add(debate)
        db_session.commit()

        mock_guard.reset_mock()

        response = authenticated_client.post(
            "/voting/test-vote-guard/predict",
            json={"predicted_winner": "GPT-4o", "confidence_score": 0.7},
        )
        assert response.status_code == 200
        mock_guard.assert_called_once()
        call_kwargs = mock_guard.call_args[1]
        assert call_kwargs["action"] == "voting_prediction"
        assert call_kwargs["debate_id"] == "test-vote-guard"

    @patch("routes.arena.require_llm_action_allowed")
    def test_arena_divergence_calls_guard(self, mock_guard, authenticated_client, db_session):
        """GET /arena/{id}/divergence calls guard before LLM recompute."""
        from models import Debate

        user_id = _get_user_id(authenticated_client, db_session)

        debate = Debate(
            id="test-div-guard",
            user_id=user_id,
            prompt="Test divergence prompt",
            mode="arena",
            status="completed",
        )
        db_session.add(debate)
        db_session.commit()

        mock_guard.reset_mock()

        # This will trigger the guard (no divergence report exists, debate is completed)
        # The LLM call itself may fail, but the guard should be called
        response = authenticated_client.get("/arena/test-div-guard/divergence")
        # Guard should have been called
        mock_guard.assert_called_once()
        call_kwargs = mock_guard.call_args[1]
        assert call_kwargs["action"] == "divergence_recompute"
        assert call_kwargs["debate_id"] == "test-div-guard"

    def test_oracle_guard_denial_prevents_session_creation(self, authenticated_client, db_session):
        """When guard denies, no OracleSession should be created."""
        from models import OracleSession

        # Exhaust credits to trigger guard denial
        user = db_session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(
                __import__("models", fromlist=["User"]).User
            ).where(
                __import__("models", fromlist=["User"]).User.email == "normal@example.com"
            )
        ).first()
        user.hosted_credits_used = 999
        user.hosted_credits_limit = 10
        db_session.add(user)
        db_session.commit()

        count_before = db_session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(OracleSession)
        ).all()

        response = authenticated_client.post(
            "/oracle",
            json={"prompt": "This should be blocked by guard"},
        )
        assert response.status_code in (400, 429)

        count_after = db_session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(OracleSession)
        ).all()
        assert len(count_after) == len(count_before)
