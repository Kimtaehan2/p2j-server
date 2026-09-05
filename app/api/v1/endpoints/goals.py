"""/goals/* (API 명세 §4). 로직은 services/goals.py."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response

from app.core.deps import CurrentUser, DbSession
from app.core.response import no_content, ok, paged
from app.schemas.goal import GoalCreateRequest, GoalUpdateRequest
from app.services import goals as svc

router = APIRouter(prefix="/goals", tags=["goals"])

StatusFilter = Literal["active", "completed", "archived"]


@router.get("", summary="목록 (status 필터, 커서)")
async def list_goals(
    user: CurrentUser,
    db: DbSession,
    status: StatusFilter | None = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
) -> dict[str, Any]:
    items, next_cursor = await svc.list_goals(db, user, status, cursor, limit)
    return paged(items, next_cursor)


@router.post("", status_code=201, summary="생성")
async def create(user: CurrentUser, db: DbSession, body: GoalCreateRequest) -> dict[str, Any]:
    return ok(await svc.serialize(db, await svc.create_goal(db, user, body)))


@router.get("/{goal_id}", summary="상세")
async def get_one(user: CurrentUser, db: DbSession, goal_id: int) -> dict[str, Any]:
    return ok(await svc.serialize(db, await svc.get_owned_goal(db, user, goal_id)))


@router.patch("/{goal_id}", summary="수정 (title·color·duration_weeks·estimated_minutes·status)")
async def update(
    user: CurrentUser, db: DbSession, goal_id: int, body: GoalUpdateRequest
) -> dict[str, Any]:
    return ok(await svc.serialize(db, await svc.update_goal(db, user, goal_id, body)))


@router.post("/{goal_id}/archive", summary="보관")
async def archive(user: CurrentUser, db: DbSession, goal_id: int) -> dict[str, Any]:
    return ok(await svc.serialize(db, await svc.archive_goal(db, user, goal_id)))


@router.delete("/{goal_id}", status_code=204, summary="삭제 (TODO 는 goal_id=null) [결정 필요 A8]")
async def delete(user: CurrentUser, db: DbSession, goal_id: int) -> Response:
    await svc.delete_goal(db, user, goal_id)
    return no_content()
