from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.services import briefing

router = APIRouter()


@router.get("")
async def get_daily_briefing(user: dict = Depends(get_current_user)):
    return await briefing.get_briefing(user["sub"])
