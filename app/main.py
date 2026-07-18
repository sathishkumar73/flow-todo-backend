from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import tasks, blog
from app.services.db.pool import open_pool, close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(title="Flow Todo API", version="0.1.0", lifespan=lifespan)

_origins = [settings.frontend_url]
if settings.frontend_url.startswith("https://"):
    bare = settings.frontend_url[len("https://"):]
    if not bare.startswith("www."):
        _origins.append(f"https://www.{bare}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(blog.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
