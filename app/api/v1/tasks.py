from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user, require_pro
from app.schemas.tasks import ReorderRequest, SharpenRequest, TaskCreate, TaskUpdate, TriageRequest
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

    ai = await ai_scoring.score_task(body.title)
    if ai:
        task = await db.create_task(
            body.title,
            user_id,
            eisenhower_quadrant=ai["eisenhower_quadrant"],
            impact_effort_quadrant=ai["impact_effort_quadrant"],
            priority_score=scoring.compute_priority_score(
                ai["eisenhower_quadrant"], ai["impact_effort_quadrant"]
            ),
            ai_rationale=ai["rationale"],
            duration_minutes=ai["duration_minutes"],
            due_date=ai["due_date"],
            ai_scored=True,
        )
    else:
        task = await db.create_task(body.title, user_id)
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
    existing = await db.get_task(task_id, user_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if body.action == "do_this_week":
        task = await db.triage_do_this_week(task_id, user_id)
        return {"task": task}
    if body.action == "someday":
        task = await db.triage_someday(task_id, user_id)
        return {"task": task}
    await db.delete_task(task_id, user_id)
    return {"ok": True}


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
    existing = await db.get_task(task_id, user_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    new_status = body.status if body.status is not None else existing["status"]
    new_eisenhower = (
        body.eisenhower_quadrant
        if body.eisenhower_quadrant is not None
        else existing["eisenhower_quadrant"]
    )
    new_impact_effort = (
        body.impact_effort_quadrant
        if body.impact_effort_quadrant is not None
        else existing["impact_effort_quadrant"]
    )
    new_score = scoring.compute_priority_score(new_eisenhower, new_impact_effort)

    task = await db.update_task(
        task_id=task_id,
        user_id=user_id,
        status=new_status,
        eisenhower_quadrant=new_eisenhower,
        impact_effort_quadrant=new_impact_effort,
        priority_score=new_score,
    )
    return {"task": task}


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(task_id: int, user: dict = Depends(get_current_user)):
    user_id: str = user["sub"]
    existing = await db.get_task(task_id, user_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.delete_task(task_id, user_id)
    return {"ok": True}
