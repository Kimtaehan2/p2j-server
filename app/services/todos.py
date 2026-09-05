"""TODO 비즈니스 로직 (API 명세 §5).

소유권: 다른 사용자의 todo 는 존재를 숨기고 404 TODO_NOT_FOUND (§1.6).
날짜: 모든 "오늘"은 service_today(). 시각은 now_utc().
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AppError,
    DeclaredTodoLocked,
    FieldValidationError,
    GoalNotFound,
    TodoNotFound,
)
from app.core.time import now_utc, service_today, week_range
from app.db.models.goal import Goal
from app.db.models.todo import Todo
from app.db.models.user import User
from app.schemas.todo import (
    TodoCompleteRequest,
    TodoCreateRequest,
    TodoPostponeRequest,
    TodoUpdateRequest,
    summary_dict,
    todo_to_dict,
)

DATE_PAST_LIMIT_DAYS = 30
DATE_FUTURE_LIMIT_DAYS = 365


# ---- 조회 -------------------------------------------------------------------------


def _alive(user: User):  # type: ignore[no-untyped-def]
    return select(Todo).where(Todo.user_id == user.user_id, Todo.deleted_at.is_(None))


async def get_owned_todo(db: AsyncSession, user: User, todo_id: int) -> Todo:
    todo = await db.scalar(_alive(user).where(Todo.todo_id == todo_id))
    if todo is None:
        raise TodoNotFound()
    return todo


async def list_day(db: AsyncSession, user: User, day: date | None) -> dict[str, Any]:
    target = day or service_today()
    rows = (
        await db.scalars(
            _alive(user).where(Todo.date == target).order_by(Todo.display_order, Todo.todo_id)
        )
    ).all()
    todos = list(rows)
    return {
        "date": target.isoformat(),
        "items": [todo_to_dict(t) for t in todos],
        "summary": summary_dict(todos),
        # 12주차 선언 구현 전까지 null. 모바일은 없어도 파싱이 깨지지 않는다 (§5).
        "declaration": None,
    }


async def week_strip(db: AsyncSession, user: User, start: date | None) -> list[dict[str, Any]]:
    """7일 달성률. 지금은 전부 실시간 집계. user_daily_stats 가 생기면 과거 일자는 거기서 읽는다."""
    first = start or (service_today() - timedelta(days=6))
    last = first + timedelta(days=6)
    rows = await db.execute(
        select(
            Todo.date,
            func.count(Todo.todo_id),
            func.count(Todo.todo_id).filter(Todo.status == "done"),
        )
        .where(
            Todo.user_id == user.user_id,
            Todo.deleted_at.is_(None),
            Todo.date >= first,
            Todo.date <= last,
        )
        .group_by(Todo.date)
    )
    by_date = {row[0]: (row[1], row[2]) for row in rows}
    out = []
    for i in range(7):
        day = first + timedelta(days=i)
        total, done = by_date.get(day, (0, 0))
        out.append(
            {
                "date": day.isoformat(),
                "total": total,
                "done": done,
                "achievement_rate": round(done / total, 2) if total else 0.0,
            }
        )
    return out


# ---- 생성·수정·삭제 --------------------------------------------------------------------


def _check_date_range(day: date, today: date) -> None:
    if not (
        today - timedelta(days=DATE_PAST_LIMIT_DAYS)
        <= day
        <= today + timedelta(days=DATE_FUTURE_LIMIT_DAYS)
    ):
        raise FieldValidationError({"date": "30일 전부터 1년 뒤까지의 날짜만 고를 수 있어요."})


async def _resolve_goal(db: AsyncSession, user: User, goal_id: int | None) -> Goal | None:
    if goal_id is None:
        return None
    goal = await db.scalar(
        select(Goal).where(
            Goal.goal_id == goal_id, Goal.user_id == user.user_id, Goal.deleted_at.is_(None)
        )
    )
    if goal is None:
        raise GoalNotFound()
    if goal.status == "archived":
        raise FieldValidationError({"goal_id": "보관한 목표에는 할 일을 붙일 수 없어요."})
    return goal


async def _next_order(db: AsyncSession, user: User, day: date) -> int:
    current = await db.scalar(
        select(func.max(Todo.display_order)).where(
            Todo.user_id == user.user_id, Todo.date == day, Todo.deleted_at.is_(None)
        )
    )
    return (current or 0) + 1


async def create_todo(db: AsyncSession, user: User, body: TodoCreateRequest) -> Todo:
    today = service_today()
    day = body.date or today
    _check_date_range(day, today)
    goal = await _resolve_goal(db, user, body.goal_id)

    todo = Todo(
        user_id=user.user_id,
        goal_id=goal.goal_id if goal else None,
        title=body.title,
        date=day,
        source="manual",
        estimated_minutes=body.estimated_minutes,
        memo=body.memo,
        display_order=await _next_order(db, user, day),
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


LOCKED_FIELDS = {"title", "date", "goal_id"}


async def update_todo(db: AsyncSession, user: User, todo_id: int, body: TodoUpdateRequest) -> Todo:
    todo = await get_owned_todo(db, user, todo_id)
    changed = body.model_fields_set

    if todo.is_declared and changed & LOCKED_FIELDS:
        raise DeclaredTodoLocked()

    if "date" in changed and body.date is not None and body.date != todo.date:
        if todo.status == "done":
            raise AppError("TODO_ALREADY_DONE", "완료한 할 일은 날짜를 바꿀 수 없어요.")
        _check_date_range(body.date, service_today())
        if body.date > todo.date:
            todo.postpone_count += 1  # BR-03: 직접 날짜 편집도 미루기로 센다
        # autoflush 때문에 날짜를 바꾸기 전에 순서를 구해야 자기 자신을 세지 않는다
        todo.display_order = await _next_order(db, user, body.date)
        todo.date = body.date

    if "goal_id" in changed:
        goal = await _resolve_goal(db, user, body.goal_id)
        todo.goal_id = goal.goal_id if goal else None
    if "title" in changed and body.title is not None:
        todo.title = body.title
    if "estimated_minutes" in changed:
        todo.estimated_minutes = body.estimated_minutes
    if "order" in changed and body.order is not None:
        todo.display_order = body.order
    if "memo" in changed:
        todo.memo = body.memo

    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, user: User, todo_id: int) -> None:
    todo = await get_owned_todo(db, user, todo_id)
    if todo.is_declared:
        raise DeclaredTodoLocked()
    todo.deleted_at = now_utc()
    await db.flush()


# ---- 상태 -------------------------------------------------------------------------


async def complete_todo(
    db: AsyncSession, user: User, todo_id: int, body: TodoCompleteRequest
) -> dict[str, Any]:
    todo = await get_owned_todo(db, user, todo_id)
    if todo.status != "done":  # 이미 done 이면 멱등 — completed_at 을 갱신하지 않는다
        todo.status = "done"
        todo.completed_at = now_utc()
        todo.actual_minutes = body.actual_minutes or todo.estimated_minutes
        await db.flush()
        await db.refresh(todo)

    return {
        "todo": todo_to_dict(todo),
        "goal_progress": await goal_progress(db, todo.goal) if todo.goal else None,
        # 선언 기능(12주차) 전에는 연속 기록을 계산할 근거가 없다.
        "personal_streak": 0,
    }


async def uncomplete_todo(db: AsyncSession, user: User, todo_id: int) -> None:
    todo = await get_owned_todo(db, user, todo_id)
    todo.status = "pending"
    todo.completed_at = None
    todo.actual_minutes = None
    await db.flush()


async def postpone_todo(
    db: AsyncSession, user: User, todo_id: int, body: TodoPostponeRequest
) -> Todo:
    todo = await get_owned_todo(db, user, todo_id)
    if todo.status == "done":
        raise AppError("TODO_ALREADY_DONE", "완료한 할 일은 미룰 수 없어요.")
    target = body.to_date or (todo.date + timedelta(days=1))
    if target <= todo.date:
        raise FieldValidationError({"to_date": "지금 날짜보다 뒤로만 미룰 수 있어요."})
    _check_date_range(target, service_today())

    todo.display_order = await _next_order(db, user, target)  # 날짜 변경 전에 (autoflush)
    todo.date = target
    todo.postpone_count += 1
    # 선언된 항목을 미루면 선언에서 빠진다. 스냅샷 상태 갱신·피드 이벤트는 12주차에.
    todo.declared_at = None
    await db.flush()
    await db.refresh(todo)
    return todo


# ---- 목표 진행률 ---------------------------------------------------------------------


async def goal_progress(db: AsyncSession, goal: Goal) -> dict[str, Any]:
    """Goal.progress (§1.7). 목표 수가 적어 요청 시점에 계산한다."""
    monday, sunday = week_range(service_today())
    row = (
        await db.execute(
            select(
                func.count(Todo.todo_id).filter(Todo.status == "done"),
                func.count(Todo.todo_id).filter(
                    Todo.status == "done", Todo.date >= monday, Todo.date <= sunday
                ),
            ).where(Todo.goal_id == goal.goal_id, Todo.deleted_at.is_(None))
        )
    ).one()
    done_count, week_done = int(row[0]), int(row[1])

    if goal.type == "recurring" and goal.frequency_times:
        weeks = goal.duration_weeks or 1
        per_week = (
            goal.frequency_times
            if goal.frequency_per == "week"
            else max(goal.frequency_times // 4, 1)
        )
        target = goal.frequency_times * (
            weeks if goal.frequency_per == "week" else max(weeks // 4, 1)
        )
        week_target = per_week
    else:
        target, week_target = 1, 1

    return {
        "goal_id": goal.goal_id,
        "target_count": target,
        "done_count": done_count,
        "achievement_rate": round(min(done_count / target, 1.0), 2) if target else 0.0,
        "current_week_done": week_done,
        "current_week_target": week_target,
    }
