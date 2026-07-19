import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user, require_pro
from app.schemas.tasks import BulkTaskCreate, ReorderRequest, SharpenRequest, TaskCreate, TaskUpdate, TriageRequest
from app.services import ai_scoring, scoring, sharpen
from app.services.db import tasks as db

router = APIRouter()


@router.get("")
async def list_tasks(user: dict = Depends(get_current_user)):
    user_id: str = user["sub"]
    tasks = await db.get_tasks(user_id)
    for t in tasks:
        t["effective_priority"] = scoring.effective_priority(
            t["priority_score"], t["due_date"]
        )
    return {"tasks": tasks}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, user: dict = Depends(get_current_user)):
    user_id: str = user["sub"]
    task = await db.create_task(body.title, user_id, focus_today=body.focus_today)
    asyncio.create_task(_score_bulk_background([task], user_id))
    return {"task": task}


@router.get("/triage")
async def get_triage(user: dict = Depends(require_pro)):
    """Tasks untouched for 14+ days — candidates for the Weekly Triage flow."""
    stale = await db.get_stale_tasks(user["sub"])
    return {"tasks": stale}


@router.post("/{task_id}/triage")
async def triage_task(
    task_id: int,
    body: TriageRequest,
    user: dict = Depends(require_pro),
):
    user_id: str = user["sub"]
    if body.action == "do_this_week":
        task = await db.triage_do_this_week(task_id, user_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return {"task": task}
    if body.action == "someday":
        task = await db.triage_someday(task_id, user_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return {"task": task}
    await db.delete_task(task_id, user_id)
    return {"ok": True}


async def _score_bulk_background(tasks: list[dict], user_id: str) -> None:
    """Score each bulk-dumped task individually; best-effort, runs in background."""
    for task in tasks:
        try:
            ai = await ai_scoring.score_task(task["title"])
            if ai:
                await db.apply_ai_score(
                    task_id=task["id"],
                    user_id=user_id,
                    eisenhower_quadrant=ai["eisenhower_quadrant"],
                    impact_effort_quadrant=ai["impact_effort_quadrant"],
                    priority_score=scoring.compute_priority_score(
                        ai["eisenhower_quadrant"], ai["impact_effort_quadrant"]
                    ),
                    ai_rationale=ai["rationale"],
                    duration_minutes=ai["duration_minutes"],
                    due_date=ai["due_date"],
                )
        except Exception:
            pass
        # small yield so we don't block the event loop for large dumps
        await asyncio.sleep(0.05)


@router.get("/all")
async def get_all_tasks(user: dict = Depends(get_current_user)):
    """Active + someday tasks for the search/review screen."""
    tasks = await db.get_all_tasks(user["sub"])
    return {"tasks": tasks}


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_tasks(body: BulkTaskCreate, user: dict = Depends(get_current_user)):
    """Brain-dump endpoint: create up to 200 tasks at once, score them in background."""
    user_id: str = user["sub"]
    tasks = await db.create_tasks_bulk(body.titles, user_id)
    asyncio.create_task(_score_bulk_background(tasks, user_id))
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/today")
async def get_today_tasks(user: dict = Depends(get_current_user)):
    """Tasks pinned to today's dump (active + done)."""
    tasks = await db.get_today_tasks(user["sub"])
    for t in tasks:
        t["effective_priority"] = scoring.effective_priority(t["priority_score"], t["due_date"])
    return {"tasks": tasks}


@router.get("/today/history")
async def get_dump_history(user: dict = Depends(get_current_user)):
    """Past daily dump tasks, grouped by date."""
    from collections import defaultdict
    tasks = await db.get_dump_history(user["sub"])
    grouped: dict[str, list] = defaultdict(list)
    for t in tasks:
        grouped[str(t["focus_date"])].append(t)
    history = [{"date": d, "tasks": ts} for d, ts in sorted(grouped.items(), reverse=True)]
    return {"history": history}


@router.post("/{task_id}/pin")
async def pin_task(task_id: int, user: dict = Depends(get_current_user)):
    """Add a task to today's dump."""
    task = await db.pin_task_today(task_id, user["sub"])
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"task": task}


@router.delete("/{task_id}/pin")
async def unpin_task(task_id: int, user: dict = Depends(get_current_user)):
    """Remove a task from today's dump (keeps the task, just removes the focus)."""
    task = await db.unpin_task_today(task_id, user["sub"])
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"task": task}


@router.get("/streak")
async def get_streak(user: dict = Depends(get_current_user)):
    """Consecutive days the user has completed at least one task."""
    return await db.get_streak(user["sub"])


@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    """Dashboard scorecard: counts, category breakdown, 7-day chart, top tasks."""
    return await db.get_dashboard_stats(user["sub"])


@router.get("/completed")
async def get_completed_tasks(user: dict = Depends(get_current_user)):
    """Tasks completed today, newest first."""
    tasks = await db.get_completed_tasks_today(user["sub"])
    return {"tasks": tasks}


@router.post("/{task_id}/promote")
async def promote_task(task_id: int, user: dict = Depends(get_current_user)):
    """Move a backlog task to the top of the stack so it enters the focus list."""
    task = await db.promote_task(task_id, user["sub"])
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"task": task}


@router.post("/reorder")
async def reorder_tasks(body: ReorderRequest, user: dict = Depends(get_current_user)):
    """Persist a new drag-and-drop order for stack mode."""
    await db.reorder_tasks(body.ordered_ids, user["sub"])
    return {"ok": True}


@router.post("/sharpen")
async def sharpen_endpoint(body: SharpenRequest, user: dict = Depends(require_pro)):
    suggestion = await sharpen.sharpen_task(body.title)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sharpen is temporarily unavailable",
        )
    return {"suggestion": suggestion}


@router.patch("/{task_id}")
async def update_task(
    task_id: int,
    body: TaskUpdate,
    user: dict = Depends(get_current_user),
):
    user_id: str = user["sub"]
    task = await db.update_task_partial(
        task_id=task_id,
        user_id=user_id,
        status=body.status,
        eisenhower_quadrant=body.eisenhower_quadrant,
        impact_effort_quadrant=body.impact_effort_quadrant,
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"task": task}


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(task_id: int, user: dict = Depends(get_current_user)):
    deleted = await db.delete_task(task_id, user["sub"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"ok": True}
