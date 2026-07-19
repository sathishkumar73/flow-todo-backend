from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from app.deps import get_current_user
from app.services.db import routines as db

router = APIRouter()


class RoutineCreate(BaseModel):
    title: str
    frequency: Literal["daily", "weekdays", "weekly", "monthly"] = "daily"
    day_of_week: int | None = None    # 0=Sun … 6=Sat
    day_of_month: int | None = None   # 1-31

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v

    model_config = {"extra": "forbid"}


@router.get("")
async def list_routines(user: dict = Depends(get_current_user)):
    return {"routines": await db.get_routines(user["sub"])}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_routine(body: RoutineCreate, user: dict = Depends(get_current_user)):
    routine = await db.create_routine(
        user["sub"], body.title, body.frequency, body.day_of_week, body.day_of_month
    )
    return {"routine": routine}


@router.post("/{routine_id}/done")
async def mark_done(routine_id: int, user: dict = Depends(get_current_user)):
    routine = await db.mark_done(routine_id, user["sub"])
    if not routine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return {"routine": routine}


@router.delete("/{routine_id}/done", status_code=status.HTTP_200_OK)
async def mark_undone(routine_id: int, user: dict = Depends(get_current_user)):
    routine = await db.mark_undone(routine_id, user["sub"])
    if not routine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return {"routine": routine}


@router.delete("/{routine_id}", status_code=status.HTTP_200_OK)
async def delete_routine(routine_id: int, user: dict = Depends(get_current_user)):
    await db.delete_routine(routine_id, user["sub"])
    return {"ok": True}
