"""TODO 요청 스키마와 응답 직렬화 (API 명세 §1.7 Todo, §5)."""

from __future__ import annotations

from datetime import date as date_type
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import to_kst_iso
from app.db.models.goal import Goal
from app.db.models.todo import Todo

# ---- 요청 -------------------------------------------------------------------------


class TodoCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    # 필드 이름 `date` 가 타입 이름을 가리므로 타입은 date_type 으로 쓴다
    date: date_type | None = None
    goal_id: int | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    memo: str | None = Field(default=None, max_length=500)


class TodoUpdateRequest(BaseModel):
    """부분 갱신. 보낸 필드만 바꾼다 (`model_fields_set`)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    # 필드 이름 `date` 가 타입 이름을 가리므로 타입은 date_type 으로 쓴다
    date: date_type | None = None
    goal_id: int | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    order: int | None = Field(default=None, ge=1)
    memo: str | None = Field(default=None, max_length=500)


class TodoCompleteRequest(BaseModel):
    actual_minutes: int | None = Field(default=None, ge=1, le=1440)


class TodoPostponeRequest(BaseModel):
    to_date: date_type | None = None


# ---- 응답 -------------------------------------------------------------------------


def todo_to_dict(todo: Todo) -> dict[str, Any]:
    goal: Goal | None = todo.goal
    return {
        "todo_id": todo.todo_id,
        "title": todo.title,
        "date": todo.date.isoformat(),
        "status": todo.status,
        "source": todo.source,
        "goal_id": todo.goal_id,
        "goal_title": goal.title if goal is not None else None,
        "estimated_minutes": todo.estimated_minutes,
        "actual_minutes": todo.actual_minutes,
        "completed_at": to_kst_iso(todo.completed_at),
        "order": todo.display_order,
        "is_declared": todo.is_declared,
        "postpone_count": todo.postpone_count,
        "proof": None,  # 12주차 proofs 구현 시 채운다
        "memo": todo.memo,
    }


def summary_dict(todos: list[Todo]) -> dict[str, Any]:
    total = len(todos)
    done = sum(1 for t in todos if t.status == "done")
    return {
        "total": total,
        "done": done,
        "achievement_rate": round(done / total, 2) if total else 0.0,
        "total_estimated_minutes": sum(t.estimated_minutes or 0 for t in todos),
    }
