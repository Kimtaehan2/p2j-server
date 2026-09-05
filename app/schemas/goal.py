"""Goal 요청 스키마와 응답 직렬화 (API 명세 §1.7 Goal, §4)."""

from __future__ import annotations

from datetime import date as date_type
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import to_kst_iso
from app.db.models.goal import Goal


class GoalFrequency(BaseModel):
    times: int = Field(ge=1, le=14)
    per: Literal["week", "month"]


class GoalCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=50)
    type: Literal["single", "recurring"] = "single"
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    frequency: GoalFrequency | None = None
    duration_weeks: int | None = Field(default=None, ge=1, le=52)
    start_date: date_type | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


class GoalUpdateRequest(BaseModel):
    """type · frequency · start_date 는 바꿀 수 없다 (진행률 의미가 깨짐, §4)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    duration_weeks: int | None = Field(default=None, ge=1, le=52)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    status: Literal["active", "completed"] | None = None


def goal_to_dict(goal: Goal, progress: dict[str, Any]) -> dict[str, Any]:
    frequency = (
        {"times": goal.frequency_times, "per": goal.frequency_per}
        if goal.type == "recurring"
        else None
    )
    return {
        "goal_id": goal.goal_id,
        "title": goal.title,
        "type": goal.type,
        "status": goal.status,
        "color": goal.color,
        "frequency": frequency,
        "duration_weeks": goal.duration_weeks if goal.type == "recurring" else None,
        "start_date": goal.start_date.isoformat(),
        "end_date": goal.end_date.isoformat() if goal.end_date else None,
        "estimated_minutes": goal.estimated_minutes,
        "progress": progress,
        "created_at": to_kst_iso(goal.created_at),
    }
