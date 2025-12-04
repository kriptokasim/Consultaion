from typing import Optional
import httpx
from loguru import logger

from core.settings import settings

GIPHY_EMPTY_STATE_TAG = "thinking"
GIPHY_CELEBRATION_TAG = "celebration"

async def fetch_giphy_gif(tag: str) -> Optional[str]:
    cfg = settings.giphy
    if not cfg.enable_giphy or not cfg.giphy_api_key:
        return None

    params = {
        "api_key": cfg.giphy_api_key,
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
