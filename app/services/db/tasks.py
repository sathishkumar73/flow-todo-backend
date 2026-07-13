from app.services.db.core import execute, query, query_one

_SELECT = """
    SELECT id, title, status, created_at, completed_at,
           eisenhower_quadrant, impact_effort_quadrant,
           priority_score, stack_position
    FROM tasks
"""


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


async def create_task(title: str, user_id: str) -> dict:
    return await query_one(
        f"""
        INSERT INTO tasks (title, status, user_id)
        VALUES (%s, 'active', %s)
        RETURNING id, title, status, created_at, completed_at,
                  eisenhower_quadrant, impact_effort_quadrant,
                  priority_score, stack_position
        """,
        (title, user_id),
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
            completed_at = CASE
                WHEN %s = 'done' AND status <> 'done' THEN now()
                WHEN %s = 'active' THEN NULL
                ELSE completed_at
            END
        WHERE id = %s AND user_id = %s
        RETURNING id, title, status, created_at, completed_at,
                  eisenhower_quadrant, impact_effort_quadrant,
                  priority_score, stack_position
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
