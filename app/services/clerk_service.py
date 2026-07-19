import logging
import time

import httpx
from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger("flow.auth")

_jwks_cache: dict | None = None


async def _get_jwks() -> tuple[dict, bool]:
    """Returns (jwks, was_cached)."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache, True
    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.clerk_jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    ms = (time.perf_counter() - t0) * 1000
    logger.info("auth.jwks_fetch  %.0fms  (cold)", ms)
    return _jwks_cache, False


async def verify_clerk_token(token: str) -> dict:
    t0 = time.perf_counter()
    try:
        jwks, cached = await _get_jwks()
        payload = jwt.decode(token, jwks, algorithms=["RS256"])
        ms = (time.perf_counter() - t0) * 1000
        logger.info("auth.verify  %.0fms  jwks_cached=%s  sub=%.8s…", ms, cached, payload.get("sub", "?"))
        return payload
    except JWTError as exc:
        ms = (time.perf_counter() - t0) * 1000
        logger.warning("auth.verify  %.0fms  [invalid] %s", ms, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )
