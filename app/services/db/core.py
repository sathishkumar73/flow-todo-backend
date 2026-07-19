import logging
import time
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from app.services.db.pool import get_pool

logger = logging.getLogger("flow.db")


def _to_json(v):
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _sql_label(sql: str) -> str:
    """Return a compact one-line label for logging (first non-blank line, truncated)."""
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:72]
    return sql[:72]


async def query(sql: str, params: tuple = ()) -> list[dict]:
    pool = get_pool()
    t0 = time.perf_counter()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
    ms = (time.perf_counter() - t0) * 1000
    logger.info("db.query  %.0fms  rows=%d  | %s", ms, len(rows), _sql_label(sql))
    return [{k: _to_json(v) for k, v in row.items()} for row in rows]


async def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = await query(sql, params)
    return rows[0] if rows else None


async def execute(sql: str, params: tuple = ()) -> None:
    pool = get_pool()
    t0 = time.perf_counter()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
    ms = (time.perf_counter() - t0) * 1000
    logger.info("db.exec   %.0fms  | %s", ms, _sql_label(sql))


async def upsert(table: str, data: dict, conflict: str) -> dict | None:
    cols = list(data.keys())
    conflict_cols = [c.strip() for c in conflict.split(",")]
    update_cols = [c for c in cols if c not in conflict_cols]
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join("%s" for _ in cols)
    conflict_list = ", ".join(f'"{c}"' for c in conflict_cols)
    if update_cols:
        updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
        on_conflict = f"ON CONFLICT ({conflict_list}) DO UPDATE SET {updates}"
    else:
        on_conflict = f"ON CONFLICT ({conflict_list}) DO NOTHING"
    sql_text = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) {on_conflict} RETURNING *'
    return await query_one(sql_text, tuple(data[c] for c in cols))


async def update(table: str, data: dict, where: dict) -> dict | None:
    set_parts = ", ".join(f'"{c}" = %s' for c in data)
    where_parts = " AND ".join(f'"{c}" = %s' for c in where)
    sql_text = f'UPDATE "{table}" SET {set_parts} WHERE {where_parts} RETURNING *'
    return await query_one(sql_text, tuple(list(data.values()) + list(where.values())))
