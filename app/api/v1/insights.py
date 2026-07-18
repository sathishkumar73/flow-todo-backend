from fastapi import APIRouter, Depends

from app.deps import require_pro
from app.services import insights

router = APIRouter()


@router.get("")
async def get_insights(user: dict = Depends(require_pro)):
    return await insights.get_insights(user["sub"])


@router.get("/retrospective")
async def get_retrospective(user: dict = Depends(require_pro)):
    return await insights.get_retrospective(user["sub"])
