from typing import Literal
from pydantic import BaseModel, field_validator

EisenhowerQuadrant = Literal["do_first", "schedule", "delegate", "eliminate"]
ImpactEffortQuadrant = Literal["quick_win", "major_project", "fill_in", "thankless"]


class TaskCreate(BaseModel):
    title: str
    focus_today: bool = False  # if true, pin this task to today's dump on creation

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v


class TaskUpdate(BaseModel):
    status: Literal["active", "done", "someday"] | None = None
    eisenhower_quadrant: EisenhowerQuadrant | None = None
    impact_effort_quadrant: ImpactEffortQuadrant | None = None

    model_config = {"extra": "forbid"}


class TriageRequest(BaseModel):
    action: Literal["do_this_week", "someday", "delete"]

    model_config = {"extra": "forbid"}


class BulkTaskCreate(BaseModel):
    titles: list[str]

    @field_validator("titles")
    @classmethod
    def validate_titles(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t.strip()]
        if not cleaned:
            raise ValueError("No valid titles provided")
        if len(cleaned) > 200:
            raise ValueError("Maximum 200 tasks per dump")
        return cleaned

    model_config = {"extra": "forbid"}


class ReorderRequest(BaseModel):
    ordered_ids: list[int]

    model_config = {"extra": "forbid"}


class SharpenRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v
