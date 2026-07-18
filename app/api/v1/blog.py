import math
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from app.services.db.core import query, query_one, upsert, update
from app.services.indexnow import submit_blog_url, submit_urls
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blog", tags=["blog"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class BlogPost(BaseModel):
    id: str
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    thumbnail_url: Optional[str] = None
    category: str
    tags: List[str] = []
    featured_image: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    published: bool
    published_at: Optional[str] = None
    created_at: str
    updated_at: str
    view_count: int = 0
    read_time: Optional[int] = None
    author_name: str
    author_avatar: Optional[str] = None


class BlogPostsResponse(BaseModel):
    posts: List[BlogPost]
    total_pages: int
    total_posts: int
    page: int
    limit: int


class BlogCategoriesResponse(BaseModel):
    categories: List[dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/posts", response_model=BlogPostsResponse)
async def get_blog_posts(
    page: int = Query(default=1, ge=1, le=1000),
    limit: int = Query(default=12, ge=1, le=1000),
    category: Optional[str] = Query(default=None, max_length=100),
    search: Optional[str] = Query(default=None, max_length=200),
):
    try:
        conditions = ["published = TRUE"]
        params: list = []

        if category and category != "all":
            conditions.append("category = %s")
            params.append(category)

        if search:
            safe = search.replace("%", "").replace("_", "").strip()
            if safe:
                conditions.append("(title ILIKE %s OR excerpt ILIKE %s)")
                params.extend([f"%{safe}%", f"%{safe}%"])

        where = " AND ".join(conditions)
        total_row = await query_one(f"SELECT COUNT(*) AS count FROM blog_posts WHERE {where}", tuple(params))
        total_posts = total_row["count"] if total_row else 0
        total_pages = (total_posts + limit - 1) // limit if total_posts > 0 else 0
        offset = (page - 1) * limit

        posts = await query(
            f"SELECT * FROM blog_posts WHERE {where} ORDER BY published_at DESC LIMIT %s OFFSET %s",
            tuple(params + [limit, offset]),
        )
        return BlogPostsResponse(posts=posts, total_pages=total_pages, total_posts=total_posts, page=page, limit=limit)
    except Exception as e:
        logger.error(f"get_blog_posts error: {e}")
        return BlogPostsResponse(posts=[], total_pages=0, total_posts=0, page=page, limit=limit)


@router.get("/posts/{slug}", response_model=BlogPost)
async def get_blog_post(slug: str):
    try:
        post = await query_one("SELECT * FROM blog_posts WHERE slug = %s AND published = TRUE", (slug,))
        if not post:
            raise HTTPException(status_code=404, detail="Blog post not found")
        asyncio.ensure_future(
            update("blog_posts", {"view_count": (post.get("view_count") or 0) + 1}, {"id": str(post["id"])})
        )
        return post
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_blog_post error: {e}")
        raise HTTPException(status_code=404, detail="Blog post not found")


@router.get("/categories", response_model=BlogCategoriesResponse)
async def get_blog_categories():
    try:
        rows = await query("SELECT DISTINCT category FROM blog_posts WHERE published = TRUE AND category IS NOT NULL")
        categories = [
            {"name": r["category"].replace("-", " ").title(), "slug": r["category"]}
            for r in sorted(rows, key=lambda r: r["category"])
        ]
        return BlogCategoriesResponse(categories=categories)
    except Exception as e:
        logger.error(f"get_blog_categories error: {e}")
        return BlogCategoriesResponse(categories=[])


@router.get("/posts/{slug}/related", response_model=List[BlogPost])
async def get_related_posts(slug: str, limit: int = Query(default=3, ge=1, le=10)):
    try:
        current = await query_one(
            "SELECT id, category FROM blog_posts WHERE slug = %s AND published = TRUE", (slug,)
        )
        if not current:
            return []
        return await query(
            "SELECT * FROM blog_posts WHERE published = TRUE AND category = %s AND id != %s ORDER BY published_at DESC LIMIT %s",
            (current["category"], current["id"], limit),
        )
    except Exception as e:
        logger.error(f"get_related_posts error: {e}")
        return []


# ── Outrank Webhook ───────────────────────────────────────────────────────────

def _read_time(html: str) -> int:
    return max(1, math.ceil(len(re.sub(r"<[^>]+>", "", html).split()) / 200))


def _excerpt(html: str, length: int = 160) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()
    return text if len(text) <= length else text[:length].rsplit(" ", 1)[0] + "..."


@router.post("/webhook/outrank")
async def handle_outrank_webhook(request: Request):
    if not settings.outrank_webhook_token:
        raise HTTPException(status_code=500, detail="Webhook not configured")
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth.split(" ", 1)[1] != settings.outrank_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid authorization")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if payload.get("event_type") != "publish_articles":
        return {"status": "ignored", "event_type": payload.get("event_type")}

    articles = payload.get("data", {}).get("articles", [])
    if not articles:
        return {"status": "ok", "message": "No articles"}

    results = []
    for article in articles:
        try:
            slug = article.get("slug")
            if not slug:
                results.append({"error": "Missing slug", "title": article.get("title")})
                continue
            html = article.get("content_html", "")
            tags = article.get("tags", [])
            now = datetime.now(timezone.utc).isoformat()
            row = {
                "title": article.get("title", ""),
                "slug": slug,
                "content": html,
                "excerpt": article.get("meta_description") or _excerpt(html),
                "featured_image": article.get("image_url"),
                "thumbnail_url": article.get("image_url"),
                "tags": tags,
                "category": article.get("category") or (tags[0] if tags else "general"),
                "seo_title": (article.get("title") or "")[:60],
                "seo_description": (article.get("meta_description") or "")[:160],
                "published": True,
                "published_at": article.get("created_at") or now,
                "read_time": _read_time(html),
                "author_name": "Flow Todo Team",
                "view_count": 0,
                "updated_at": now,
            }
            await upsert("blog_posts", row, conflict="slug")
            results.append({"slug": slug, "status": "ok"})
            asyncio.ensure_future(submit_blog_url(slug))
        except Exception as e:
            logger.error(f"Outrank webhook error for '{article.get('title')}': {e}")
            results.append({"slug": article.get("slug"), "error": str(e)})

    return {"status": "ok", "processed": len(results), "results": results}


# ── IndexNow Manual Submit ────────────────────────────────────────────────────

class IndexNowRequest(BaseModel):
    urls: Optional[List[str]] = None
    slugs: Optional[List[str]] = None


@router.post("/indexnow/submit")
async def submit_indexnow(body: IndexNowRequest):
    urls: List[str] = list(body.urls or [])
    for slug in (body.slugs or []):
        urls.append(f"https://flowtodo.app/blog/{slug}")
    if not urls:
        rows = await query("SELECT slug FROM blog_posts WHERE published = TRUE")
        urls = [f"https://flowtodo.app/blog/{r['slug']}" for r in rows]
    if not urls:
        return {"status": "ok", "message": "No URLs to submit"}
    success = await submit_urls(urls)
    return {"status": "ok" if success else "error", "submitted": len(urls), "urls": urls}
