from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.services.clerk_service import verify_clerk_token
from app.services.db import users as users_db

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    payload = await verify_clerk_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


async def require_pro(user: dict = Depends(get_current_user)) -> dict:
    """Gate for Pro features. A no-op until ENFORCE_PRO_GATING=true, so the
    product keeps working end-to-end before billing ships."""
    if not settings.enforce_pro_gating:
        return user
    record = await users_db.get_or_create_user(user["sub"])
    if not record["is_pro"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This feature requires Flow Todo Pro",
        )
    return user
