import logging
import logging.config
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import tasks, blog, briefing, insights, me, routines
from app.services.db.pool import open_pool, close_pool


def _setup_logging() -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "psycopg", "psycopg_pool", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_logger = logging.getLogger("flow.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logging.getLogger("flow").info("startup  log_level=%s", settings.log_level)
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


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    _logger.info(
        "%s %s → %d  %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response


app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(briefing.router, prefix="/api/v1/briefing", tags=["briefing"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])
app.include_router(me.router, prefix="/api/v1/me", tags=["me"])
app.include_router(routines.router, prefix="/api/v1/routines", tags=["routines"])
app.include_router(blog.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
