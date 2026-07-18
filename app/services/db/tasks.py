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


async def delete_task(task_id: int, user_id: str) -> None:
    await execute(
        "DELETE FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, user_id),
    )
