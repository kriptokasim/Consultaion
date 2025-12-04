import pytest
from unittest.mock import patch, AsyncMock
from httpx import Response
from models import User
from routes.auth import _profile_payload



@pytest.mark.asyncio
async def test_giphy_disabled():
    with patch("integrations.giphy.settings") as mock_settings:
        mock_settings.giphy.enable_giphy = False
        from integrations.giphy import fetch_giphy_gif
        url = await fetch_giphy_gif("tag")
        assert url is None

def test_profile_payload_debate_count():
    user = User(email="test@example.com", password_hash="hash")
    payload = _profile_payload(user, debate_count=42)
    assert payload.debate_count == 42
    
    payload_default = _profile_payload(user)
    assert payload_default.debate_count == 0
