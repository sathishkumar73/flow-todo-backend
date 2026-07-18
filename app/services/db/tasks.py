from app.services.db.core import execute, query, query_one

_COLUMNS = """id, title, status, created_at, completed_at,
           eisenhower_quadrant, impact_effort_quadrant,
           priority_score, stack_position,
           due_date, duration_minutes, ai_rationale, ai_scored, last_touched_at"""

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
                           ai_rationale, duration_minutes, due_date, ai_scored)
        VALUES (%s, 'active', %s, %s, %s, %s, %s, %s, %s, %s)
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


async def delete_task(task_id: int, user_id: str) -> None:
    await execute(
        "DELETE FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, user_id),
    )
