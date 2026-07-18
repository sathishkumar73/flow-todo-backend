from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import get_current_user
from app.services.db import users as users_db

router = APIRouter()


@router.get("")
async def get_me(user: dict = Depends(get_current_user)):
    record = await users_db.get_or_create_user(user["sub"])
    return {
        "user_id": record["user_id"],
        "is_pro": record["is_pro"],
        "pro_since": record["pro_since"],
        "pro_gating_enforced": settings.enforce_pro_gating,
    }
