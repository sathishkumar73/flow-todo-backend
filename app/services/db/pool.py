import psycopg_pool

from app.config import settings

_pool: psycopg_pool.AsyncConnectionPool | None = None


async def open_pool() -> None:
    global _pool
    _pool = psycopg_pool.AsyncConnectionPool(
        settings.database_url,
        min_size=5,
        max_size=10,
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    if _pool:
        await _pool.close()


def get_pool() -> psycopg_pool.AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised")
    return _pool
