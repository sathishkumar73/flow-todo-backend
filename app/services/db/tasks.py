import asyncio

from app.services.db.core import execute, query, query_one

_COLUMNS = """id, title, status, created_at, completed_at,
           eisenhower_quadrant, impact_effort_quadrant,
           priority_score, stack_position,
           due_date, duration_minutes, ai_rationale, ai_scored, last_touched_at,
           focus_date"""

_SELECT = f"SELECT {_COLUMNS} FROM tasks"


async def get_tasks(user_id: str) -> list[dict]:
    return await query(
        f"{_SELECT} WHERE user_id = %s ORDER BY stack_position DESC",
        (user_id,),
    )


async def get_task(task_id: int, user_id: str) -> dict | None:
    return await query_one(
        f"{_SELECT} WHERE id = %s AND user_id = %s",
        (task_id, user_id),
    )


async def create_task(
    title: str,
    user_id: str,
    focus_today: bool = False,
    eisenhower_quadrant: str | None = None,
    impact_effort_quadrant: str | None = None,
    priority_score: int = 0,
    ai_rationale: str | None = None,
    duration_minutes: int | None = None,
    due_date: str | None = None,
    ai_scored: bool = False,
) -> dict:
    return await query_one(
        f"""
        INSERT INTO tasks (title, status, user_id,
                           eisenhower_quadrant, impact_effort_quadrant, priority_score,
                           ai_rationale, duration_minutes, due_date, ai_scored,
                           focus_date)
        VALUES (%s, 'active', %s, %s, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s THEN CURRENT_DATE ELSE NULL END)
        RETURNING {_COLUMNS}
        """,
        (
            title,
            user_id,
            eisenhower_quadrant,
            impact_effort_quadrant,
            priority_score,
            ai_rationale,
            duration_minutes,
            due_date,
            ai_scored,
            focus_today,
        ),
    )


async def update_task(
    task_id: int,
    user_id: str,
    status: str,
    eisenhower_quadrant: str | None,
    impact_effort_quadrant: str | None,
    priority_score: int,
) -> dict | None:
    return await query_one(
        f"""
        UPDATE tasks
        SET status                = %s,
            eisenhower_quadrant   = %s,
            impact_effort_quadrant = %s,
            priority_score        = %s,
            last_touched_at       = now(),
            completed_at = CASE
                WHEN %s = 'done' AND status <> 'done' THEN now()
                WHEN %s = 'active' THEN NULL
                ELSE completed_at
            END
        WHERE id = %s AND user_id = %s
        RETURNING {_COLUMNS}
        """,
        (
            status,
            eisenhower_quadrant,
            impact_effort_quadrant,
            priority_score,
            status,
            status,
            task_id,
            user_id,
        ),
    )


async def update_task_partial(
    task_id: int,
    user_id: str,
    status: str | None,
    eisenhower_quadrant: str | None,
    impact_effort_quadrant: str | None,
) -> dict | None:
    """Update only the supplied fields; compute new score inside Postgres."""
    return await query_one(
        f"""
        UPDATE tasks
        SET status                 = COALESCE(%s, status),
            eisenhower_quadrant    = COALESCE(%s, eisenhower_quadrant),
            impact_effort_quadrant = COALESCE(%s, impact_effort_quadrant),
            priority_score         = (
                CASE COALESCE(%s, eisenhower_quadrant)
                  WHEN 'do_first'  THEN 40
                  WHEN 'schedule'  THEN 30
                  WHEN 'delegate'  THEN 20
                  WHEN 'eliminate' THEN 10
                  ELSE 0
                END
                +
                CASE COALESCE(%s, impact_effort_quadrant)
                  WHEN 'quick_win'      THEN 40
                  WHEN 'major_project'  THEN 30
                  WHEN 'fill_in'        THEN 20
                  WHEN 'thankless'      THEN 10
                  ELSE 0
                END
            ),
            last_touched_at        = now(),
            completed_at = CASE
                WHEN COALESCE(%s, status) = 'done'   AND status <> 'done' THEN now()
                WHEN COALESCE(%s, status) = 'active'                      THEN NULL
                ELSE completed_at
            END
        WHERE id = %s AND user_id = %s
        RETURNING {_COLUMNS}
        """,
        (
            status,
            eisenhower_quadrant,
            impact_effort_quadrant,
            eisenhower_quadrant,
            impact_effort_quadrant,
            status,
            status,
            task_id,
            user_id,
        ),
    )


async def get_stale_tasks(user_id: str, days: int = 14) -> list[dict]:
    return await query(
        f"""{_SELECT}
        WHERE user_id = %s AND status = 'active'
          AND last_touched_at < now() - make_interval(days => %s)
        ORDER BY last_touched_at ASC
        """,
        (user_id, days),
    )


async def triage_do_this_week(task_id: int, user_id: str) -> dict | None:
    # bump to the top of the stack and mark as freshly touched
    return await query_one(
        f"""
        UPDATE tasks
        SET last_touched_at = now(),
            stack_position  = nextval(pg_get_serial_sequence('tasks', 'stack_position'))
        WHERE id = %s AND user_id = %s
        RETURNING {_COLUMNS}
        """,
        (task_id, user_id),
    )


async def triage_someday(task_id: int, user_id: str) -> dict | None:
    return await query_one(
        f"""
        UPDATE tasks
        SET status = 'someday', last_touched_at = now()
        WHERE id = %s AND user_id = %s
        RETURNING {_COLUMNS}
        """,
        (task_id, user_id),
    )


async def get_all_tasks(user_id: str) -> list[dict]:
    """Active + someday tasks for search/review page."""
    return await query(
        f"""{_SELECT}
        WHERE user_id = %s AND status IN ('active', 'someday')
        ORDER BY status, stack_position DESC
        """,
        (user_id,),
    )


async def create_tasks_bulk(titles: list[str], user_id: str) -> list[dict]:
    return await query(
        f"""
        INSERT INTO tasks (title, status, user_id)
        SELECT unnest(%s::text[]), 'active', %s
        RETURNING {_COLUMNS}
        """,
        (titles, user_id),
    )


async def apply_ai_score(
    task_id: int,
    user_id: str,
    eisenhower_quadrant: str | None,
    impact_effort_quadrant: str | None,
    priority_score: int,
    ai_rationale: str | None,
    duration_minutes: int | None,
    due_date: str | None,
) -> None:
    await execute(
        """
        UPDATE tasks
        SET eisenhower_quadrant    = %s,
            impact_effort_quadrant = %s,
            priority_score         = %s,
            ai_rationale           = %s,
            duration_minutes       = COALESCE(%s, duration_minutes),
            due_date               = COALESCE(%s, due_date),
            ai_scored              = true
        WHERE id = %s AND user_id = %s AND ai_scored = false
        """,
        (
            eisenhower_quadrant,
            impact_effort_quadrant,
            priority_score,
            ai_rationale,
            duration_minutes,
            due_date,
            task_id,
            user_id,
        ),
    )


async def get_completed_tasks_today(user_id: str) -> list[dict]:
    return await query(
        f"""{_SELECT}
        WHERE user_id = %s
          AND status = 'done'
          AND completed_at >= CURRENT_DATE
        ORDER BY completed_at DESC
        LIMIT 100
        """,
        (user_id,),
    )


async def promote_task(task_id: int, user_id: str) -> dict | None:
    """Move a backlog task to the top of the stack so it enters the focus list."""
    return await query_one(
        f"""
        UPDATE tasks
        SET    stack_position = (SELECT COALESCE(MAX(stack_position), 0) + 1
                                 FROM tasks WHERE user_id = %s),
               last_touched_at = now()
        WHERE  id = %s AND user_id = %s
        RETURNING {_COLUMNS}
        """,
        (user_id, task_id, user_id),
    )


async def reorder_tasks(ordered_ids: list[int], user_id: str) -> None:
    """
    Assign stack_position so that the first id in the list sits at the top.
    Uses unnest for a single-round-trip bulk update.
    """
    n = len(ordered_ids)
    positions = list(range(n, 0, -1))  # n, n-1, …, 1
    await execute(
        """
        UPDATE tasks
        SET    stack_position = v.pos
        FROM   (SELECT unnest(%s::int[]) AS id, unnest(%s::int[]) AS pos) AS v
        WHERE  tasks.id = v.id AND tasks.user_id = %s
        """,
        (ordered_ids, positions, user_id),
    )


async def delete_task(task_id: int, user_id: str) -> bool:
    row = await query_one(
        "DELETE FROM tasks WHERE id = %s AND user_id = %s RETURNING id",
        (task_id, user_id),
    )
    return row is not None


async def get_dashboard_stats(user_id: str) -> dict:
    counts, eis_rows, ie_rows, daily_rows, top_rows = await asyncio.gather(
        query_one(
            """
            SELECT
                (SELECT count(*)::int FROM tasks WHERE user_id = %s AND status = 'active')                                AS active,
                (SELECT count(*)::int FROM tasks WHERE user_id = %s AND status = 'done'
                 AND completed_at >= CURRENT_DATE)                                                                         AS completed_today,
                (SELECT count(*)::int FROM tasks WHERE user_id = %s AND status = 'done'
                 AND completed_at >= date_trunc('week', now()))                                                            AS completed_week,
                (SELECT count(*)::int FROM tasks WHERE user_id = %s AND status = 'someday')                               AS someday,
                (SELECT count(*)::int FROM tasks WHERE user_id = %s AND status = 'active' AND ai_scored = true)           AS ai_scored
            """,
            (user_id, user_id, user_id, user_id, user_id),
        ),
        query(
            """
            SELECT COALESCE(eisenhower_quadrant, 'none') AS q, count(*)::int AS count
            FROM tasks WHERE user_id = %s AND status = 'active'
            GROUP BY 1
            """,
            (user_id,),
        ),
        query(
            """
            SELECT COALESCE(impact_effort_quadrant, 'none') AS q, count(*)::int AS count
            FROM tasks WHERE user_id = %s AND status = 'active'
            GROUP BY 1
            """,
            (user_id,),
        ),
        query(
            """
            WITH days AS (
                SELECT generate_series(CURRENT_DATE - 6, CURRENT_DATE, '1 day'::interval)::date AS day
            )
            SELECT d.day::text AS date, COALESCE(c.cnt, 0)::int AS count
            FROM days d
            LEFT JOIN (
                SELECT completed_at::date AS day, count(*)::int AS cnt
                FROM tasks
                WHERE user_id = %s AND status = 'done' AND completed_at >= CURRENT_DATE - 6
                GROUP BY 1
            ) c ON c.day = d.day
            ORDER BY 1
            """,
            (user_id,),
        ),
        query(
            """
            SELECT id, title, priority_score, eisenhower_quadrant, impact_effort_quadrant
            FROM tasks
            WHERE user_id = %s AND status = 'active' AND ai_scored = true
            ORDER BY priority_score DESC
            LIMIT 5
            """,
            (user_id,),
        ),
    )

    return {
        **counts,
        "eisenhower": {r["q"]: r["count"] for r in eis_rows},
        "impact_effort": {r["q"]: r["count"] for r in ie_rows},
        "daily_completions": daily_rows,
        "top_tasks": top_rows,
    }


async def get_today_tasks(user_id: str) -> list[dict]:
    """Tasks pinned to today's dump (focus_date = today) that are still active."""
    return await query(
        f"{_SELECT} WHERE user_id = %s AND status = 'active' AND focus_date = CURRENT_DATE ORDER BY stack_position DESC",
        (user_id,),
    )


async def pin_task_today(task_id: int, user_id: str) -> dict | None:
    return await query_one(
        f"UPDATE tasks SET focus_date = CURRENT_DATE WHERE id = %s AND user_id = %s RETURNING {_COLUMNS}",
        (task_id, user_id),
    )


async def unpin_task_today(task_id: int, user_id: str) -> dict | None:
    return await query_one(
        f"UPDATE tasks SET focus_date = NULL WHERE id = %s AND user_id = %s RETURNING {_COLUMNS}",
        (task_id, user_id),
    )
