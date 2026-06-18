from typing import Optional

import httpx
from config import settings
from loguru import logger

GIPHY_EMPTY_STATE_TAG = "thinking"
GIPHY_CELEBRATION_TAG = "celebration"

async def fetch_giphy_gif(tag: str) -> Optional[str]:
    if not settings.ENABLE_GIPHY or not settings.GIPHY_API_KEY:
        return None

    params = {
        "api_key": settings.GIPHY_API_KEY,
        "tag": tag,
        "rating": "g",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.giphy.com/v1/gifs/random", params=params)
            resp.raise_for_status()
            
        data = resp.json().get("data") or {}
        # Try to get mp4, fallback to url (gif)
        return data.get("images", {}).get("downsized_small", {}).get("mp4") or \
               data.get("images", {}).get("downsized", {}).get("url")
    except Exception as exc:
        print(f"DEBUG: Exception: {exc}")
        logger.warning("Failed to fetch Giphy GIF for tag %s: %r", tag, exc)
        return None
