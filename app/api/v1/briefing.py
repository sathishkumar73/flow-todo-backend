from fastapi import APIRouter, Depends

from app.deps import require_pro
from app.services import briefing

router = APIRouter()


@router.get("")
async def get_daily_briefing(user: dict = Depends(require_pro)):
    return await briefing.get_briefing(user["sub"])
