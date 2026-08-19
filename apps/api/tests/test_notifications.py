from unittest.mock import AsyncMock, patch

import pytest
from integrations.email import send_debate_summary_email
from integrations.slack import send_slack_alert
from schemas import DebateSummary


def _summary() -> DebateSummary:
    return DebateSummary(
        debate_id="d1",
        title="Test Debate",
        models_used=["gpt-4"],
        winner="gpt-4",
        summary_text="A great debate.",
        url="http://localhost:3000/debates/d1",
    )


@pytest.mark.anyio
async def test_send_debate_summary_email_enabled():
    with patch("integrations.email.settings") as mock_settings, patch(
        "integrations.email.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_settings.ENABLE_EMAIL_SUMMARIES = True
        mock_settings.RESEND_API_KEY = "re_123"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.raise_for_status.return_value = None

        await send_debate_summary_email("test@example.com", _summary())

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.resend.com/emails"
        assert call_args[1]["json"]["to"] == ["test@example.com"]
        assert "Test Debate" in call_args[1]["json"]["subject"]


@pytest.mark.anyio
async def test_send_debate_summary_email_disabled():
    with patch("integrations.email.settings") as mock_settings, patch(
        "integrations.email.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_settings.ENABLE_EMAIL_SUMMARIES = False
        mock_settings.RESEND_API_KEY = "re_123"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        await send_debate_summary_email("test@example.com", _summary())

        mock_client.post.assert_not_called()


@pytest.mark.anyio
async def test_send_slack_alert_enabled():
    with patch("integrations.slack.settings") as mock_settings, patch(
        "integrations.slack.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_settings.ENABLE_SLACK_ALERTS = True
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.raise_for_status.return_value = None

        await send_slack_alert("Test Alert", meta={"key": "value"})

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/services/..."
        assert "Test Alert" in call_args[1]["json"]["attachments"][0]["text"]
