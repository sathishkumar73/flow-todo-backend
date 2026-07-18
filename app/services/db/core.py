from psycopg.rows import dict_row

from app.services.db.pool import get_pool


async def query(sql: str, params: tuple = ()) -> list[dict]:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()


async def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = await query(sql, params)
    return rows[0] if rows else None


async def execute(sql: str, params: tuple = ()) -> None:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)


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
