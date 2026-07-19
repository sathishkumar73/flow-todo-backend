from app.services.db.core import query, query_one, execute

_COLS = "id, user_id, title, frequency, day_of_week, day_of_month, last_done_at, is_active, created_at"

_DUE_EXPR = """
    CASE frequency
      WHEN 'daily'    THEN true
      WHEN 'weekdays' THEN EXTRACT(dow FROM now() AT TIME ZONE 'UTC') BETWEEN 1 AND 5
      WHEN 'weekly'   THEN EXTRACT(dow FROM now() AT TIME ZONE 'UTC') = day_of_week
      WHEN 'monthly'  THEN EXTRACT(day FROM now() AT TIME ZONE 'UTC') = day_of_month
      ELSE false
    END
"""


async def get_routines(user_id: str) -> list[dict]:
    return await query(
        f"""
        SELECT {_COLS},
               (last_done_at IS NOT NULL AND last_done_at >= CURRENT_DATE) AS is_done_today,
               ({_DUE_EXPR}) AS is_due_today
        FROM routines
        WHERE user_id = %s AND is_active = true
        ORDER BY created_at ASC
        """,
        (user_id,),
    )


async def create_routine(
    user_id: str,
    title: str,
    frequency: str,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
) -> dict:
    return await query_one(
        f"""
        INSERT INTO routines (user_id, title, frequency, day_of_week, day_of_month)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING {_COLS},
                  false AS is_done_today,
                  ({_DUE_EXPR}) AS is_due_today
        """,
        (user_id, title, frequency, day_of_week, day_of_month),
    )


async def mark_done(routine_id: int, user_id: str) -> dict | None:
    return await query_one(
        f"""
        UPDATE routines SET last_done_at = now()
        WHERE id = %s AND user_id = %s
        RETURNING {_COLS},
                  true AS is_done_today,
                  ({_DUE_EXPR}) AS is_due_today
        """,
        (routine_id, user_id),
    )


async def mark_undone(routine_id: int, user_id: str) -> dict | None:
    return await query_one(
        f"""
        UPDATE routines SET last_done_at = NULL
        WHERE id = %s AND user_id = %s
        RETURNING {_COLS},
                  false AS is_done_today,
                  ({_DUE_EXPR}) AS is_due_today
        """,
        (routine_id, user_id),
    )


async def delete_routine(routine_id: int, user_id: str) -> None:
    await execute(
        "UPDATE routines SET is_active = false WHERE id = %s AND user_id = %s",
        (routine_id, user_id),
    )
