"""Goal 비즈니스 로직 (API 명세 §4). 소유권 위반은 404 GOAL_NOT_FOUND."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import FieldValidationError, GoalNotFound
from app.core.response import clamp_limit, decode_cursor, encode_cursor
from app.core.time import now_utc, service_today, week_range
from app.db.models.goal import Goal
from app.db.models.todo import Todo
from app.db.models.user import User
from app.schemas.goal import GoalCreateRequest, GoalUpdateRequest, goal_to_dict

# color 를 안 주면 여기서 순환 (사용자의 목표 수 기준)
DEFAULT_PALETTE = ("#3182F6", "#F04452", "#FF8A00", "#00A86B", "#8B5CF6", "#0EA5E9", "#F59E0B")


async def get_owned_goal(db: AsyncSession, user: User, goal_id: int) -> Goal:
    goal = await db.scalar(
        select(Goal).where(
            Goal.goal_id == goal_id, Goal.user_id == user.user_id, Goal.deleted_at.is_(None)
        )
    )
    if goal is None:
        raise GoalNotFound()
    return goal


# ---- 진행률 -------------------------------------------------------------------------


def _targets(goal: Goal) -> tuple[int, int]:
    """(전체 목표 횟수, 이번 주 목표 횟수)."""
    if goal.type != "recurring" or not goal.frequency_times:
        return 1, 1
    weeks = goal.duration_weeks or 1
    if goal.frequency_per == "week":
        return goal.frequency_times * weeks, goal.frequency_times
    months = max(weeks // 4, 1)
    return goal.frequency_times * months, max(goal.frequency_times // 4, 1)


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
    target, week_target = _targets(goal)
    return {
        "goal_id": goal.goal_id,
        "target_count": target,
        "done_count": done_count,
        "achievement_rate": round(min(done_count / target, 1.0), 2) if target else 0.0,
        "current_week_done": week_done,
        "current_week_target": week_target,
    }


async def serialize(db: AsyncSession, goal: Goal) -> dict[str, Any]:
    return goal_to_dict(goal, await goal_progress(db, goal))


# ---- 조회 -------------------------------------------------------------------------


async def list_goals(
    db: AsyncSession, user: User, status: str | None, cursor: str | None, limit: int | None
) -> tuple[list[dict[str, Any]], str | None]:
    """created_at DESC. 커서는 {"id": 마지막 goal_id} (created_at 과 id 순서가 같다)."""
    size = clamp_limit(limit)
    stmt = select(Goal).where(Goal.user_id == user.user_id, Goal.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Goal.status == status)
    decoded = decode_cursor(cursor)
    if decoded and isinstance(decoded.get("id"), int):
        stmt = stmt.where(Goal.goal_id < decoded["id"])
    rows = list((await db.scalars(stmt.order_by(Goal.goal_id.desc()).limit(size + 1))).all())

    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        next_cursor = encode_cursor({"id": rows[-1].goal_id})
    return [await serialize(db, g) for g in rows], next_cursor


# ---- 생성·수정 -------------------------------------------------------------------------


def _end_date(start: date, duration_weeks: int | None) -> date | None:
    return start + timedelta(days=duration_weeks * 7 - 1) if duration_weeks else None


async def _next_color(db: AsyncSession, user: User) -> str:
    count = await db.scalar(select(func.count(Goal.goal_id)).where(Goal.user_id == user.user_id))
    return DEFAULT_PALETTE[(count or 0) % len(DEFAULT_PALETTE)]


async def create_goal(db: AsyncSession, user: User, body: GoalCreateRequest) -> Goal:
    if body.type == "recurring" and body.frequency is None:
        raise FieldValidationError({"frequency": "반복 목표는 빈도를 정해 주세요."})
    start = body.start_date or service_today()
    recurring = body.type == "recurring"
    goal = Goal(
        user_id=user.user_id,
        title=body.title,
        type=body.type,
        color=body.color or await _next_color(db, user),
        frequency_times=body.frequency.times if recurring and body.frequency else None,
        frequency_per=body.frequency.per if recurring and body.frequency else None,
        duration_weeks=body.duration_weeks if recurring else None,
        start_date=start,
        end_date=_end_date(start, body.duration_weeks if recurring else None),
        estimated_minutes=body.estimated_minutes,
    )
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return goal


async def update_goal(db: AsyncSession, user: User, goal_id: int, body: GoalUpdateRequest) -> Goal:
    goal = await get_owned_goal(db, user, goal_id)
    changed = body.model_fields_set
    if "title" in changed and body.title is not None:
        goal.title = body.title
    if "color" in changed and body.color is not None:
        goal.color = body.color
    if "estimated_minutes" in changed:
        goal.estimated_minutes = body.estimated_minutes
    if "duration_weeks" in changed and goal.type == "recurring":
        goal.duration_weeks = body.duration_weeks
        goal.end_date = _end_date(goal.start_date, body.duration_weeks)
    if "status" in changed and body.status is not None:
        goal.status = body.status  # active ↔ completed. 보관 해제도 status=active
    await db.flush()
    await db.refresh(goal)
    return goal


async def archive_goal(db: AsyncSession, user: User, goal_id: int) -> Goal:
    goal = await get_owned_goal(db, user, goal_id)
    goal.status = "archived"  # 소속 TODO 는 그대로 (US-GOAL-02)
    await db.flush()
    await db.refresh(goal)
    return goal


async def delete_goal(db: AsyncSession, user: User, goal_id: int) -> None:
    """soft delete. 소속 TODO 는 goal_id=null (§4). [결정 필요 A8] 보관만 쓰면 이 함수를 지운다."""
    goal = await get_owned_goal(db, user, goal_id)
    goal.deleted_at = now_utc()
    await db.execute(update(Todo).where(Todo.goal_id == goal.goal_id).values(goal_id=None))
    await db.flush()
