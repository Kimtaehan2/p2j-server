"""/ai/* (API 명세 §6). 저장은 하지 않는다 — 저장은 POST /todos/bulk."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.response import ok
from app.schemas.ai import ParseRequest
from app.services import ai_parse as svc

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse", summary="자유 텍스트 → TODO 초안 목록 (3단계 폴백, 저장 안 함)")
async def parse(user: CurrentUser, db: DbSession, body: ParseRequest) -> dict[str, Any]:
    return ok(await svc.parse(db, user, body))


@router.get("/quota", summary="오늘 남은 AI 호출 수")
async def quota(user: CurrentUser) -> dict[str, Any]:
    return ok(await svc.quota_state(user))
