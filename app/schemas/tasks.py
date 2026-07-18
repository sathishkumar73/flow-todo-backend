from typing import Literal
from pydantic import BaseModel, field_validator

EisenhowerQuadrant = Literal["do_first", "schedule", "delegate", "eliminate"]
ImpactEffortQuadrant = Literal["quick_win", "major_project", "fill_in", "thankless"]


class TaskCreate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v


class TaskUpdate(BaseModel):
    status: Literal["active", "done"] | None = None
    eisenhower_quadrant: EisenhowerQuadrant | None = None
    impact_effort_quadrant: ImpactEffortQuadrant | None = None

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
