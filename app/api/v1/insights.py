from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.services import insights

router = APIRouter()


@router.get("")
async def get_insights(user: dict = Depends(get_current_user)):
    return await insights.get_insights(user["sub"])


@router.get("/retrospective")
async def get_retrospective(user: dict = Depends(get_current_user)):
    return await insights.get_retrospective(user["sub"])
