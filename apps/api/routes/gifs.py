from fastapi import APIRouter
from pydantic import BaseModel
from integrations.giphy import fetch_giphy_gif, GIPHY_EMPTY_STATE_TAG, GIPHY_CELEBRATION_TAG

router = APIRouter()

class GifResponse(BaseModel):
    url: str | None

@router.get("/empty-state", response_model=GifResponse)
async def get_empty_state_gif():
    url = await fetch_giphy_gif(GIPHY_EMPTY_STATE_TAG)
    return GifResponse(url=url)

@router.get("/celebration", response_model=GifResponse)
async def get_celebration_gif():
    url = await fetch_giphy_gif(GIPHY_CELEBRATION_TAG)
    return GifResponse(url=url)
