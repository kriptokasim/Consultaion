from config import settings
from fastapi import APIRouter
from integrations.giphy import GIPHY_CELEBRATION_TAG, GIPHY_EMPTY_STATE_TAG, fetch_giphy_gif
from pydantic import BaseModel

router = APIRouter()

class GifResponse(BaseModel):
    url: str | None

@router.get("/empty-state", response_model=GifResponse)
async def get_empty_state_gif():
    if not settings.ENABLE_GIPHY:
        return GifResponse(url=None)
    url = await fetch_giphy_gif(GIPHY_EMPTY_STATE_TAG)
    return GifResponse(url=url)

@router.get("/celebration", response_model=GifResponse)
async def get_celebration_gif():
    if not settings.ENABLE_GIPHY:
        return GifResponse(url=None)
    url = await fetch_giphy_gif(GIPHY_CELEBRATION_TAG)
    return GifResponse(url=url)
