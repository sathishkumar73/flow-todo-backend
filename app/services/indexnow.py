import httpx
import logging
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"
HOST = "flowtodo.app"
KEY_LOCATION = f"https://{HOST}/{settings.indexnow_api_key}.txt"


async def submit_urls(urls: List[str]) -> bool:
    if not urls:
        return True
    if not settings.indexnow_api_key:
        logger.warning("IndexNow: INDEXNOW_API_KEY not set, skipping")
        return False

    payload = {
        "host": HOST,
        "key": settings.indexnow_api_key,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(INDEXNOW_ENDPOINT, json=payload)
        if resp.status_code in (200, 202):
            logger.info(f"IndexNow: submitted {len(urls)} URL(s) — {resp.status_code}")
            return True
        logger.warning(f"IndexNow: unexpected {resp.status_code} — {resp.text[:200]}")
        return False
    except Exception as e:
        logger.warning(f"IndexNow: submission failed — {e}")
        return False


async def submit_blog_url(slug: str) -> bool:
    return await submit_urls([f"https://{HOST}/blog/{slug}"])
