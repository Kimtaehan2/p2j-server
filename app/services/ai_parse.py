"""POST /ai/parse 서비스 — 목표 힌트 조회 · 쿼터 · 파이프라인 호출 · 응답 조립 (§6)."""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import service_today
from app.db.models.goal import Goal
from app.db.models.user import User
from app.schemas.ai import ParseRequest
from app.services.ai import pipeline, quota
from app.services.ai.schemas import GoalHint


async def _goal_hints(db: AsyncSession, user: User, goal_ids: list[int] | None) -> list[GoalHint]:
    stmt = select(Goal).where(
        Goal.user_id == user.user_id, Goal.deleted_at.is_(None), Goal.status == "active"
    )
    if goal_ids:
        stmt = stmt.where(Goal.goal_id.in_(goal_ids))
    rows = await db.scalars(stmt)
    return [
        GoalHint(goal_id=g.goal_id, title=g.title, estimated_minutes=g.estimated_minutes)
        for g in rows
    ]


async def parse(db: AsyncSession, user: User, body: ParseRequest) -> dict[str, Any]:
    state, minute_exceeded, day_exceeded = await quota.consume(user.user_id)
    if minute_exceeded:
        raise AppError("AI_QUOTA_EXCEEDED")

    ref_date = body.reference_date or service_today()
    goals = await _goal_hints(db, user, body.context.goal_ids if body.context else None)

    # 일 한도 초과: 429 대신 규칙 파서로 (§6 GET /ai/quota)
    result = await pipeline.parse(body.text, ref_date, goals, allow_llm=not day_exceeded)
    warnings = list(result.warnings)
    if day_exceeded:
        warnings.append("quota_exceeded")

    return {
        "parse_id": f"prs_{secrets.token_hex(4)}",  # 저장하지 않는다. bulk 와 연결용 식별자
        "parse_method": result.method,
        "drafts": [
            {"draft_id": f"d{i + 1}", **d.model_dump(mode="json")}
            for i, d in enumerate(result.drafts)
        ],
        "warnings": warnings,
        "quota": {"remaining_today": state.remaining_today, "reset_at": state.reset_at},
    }


async def quota_state(user: User) -> dict[str, Any]:
    return (await quota.get_state(user.user_id)).to_dict()
