"""파이프라인 공용 데이터 구조. LLM 구조화 출력의 response_format 으로도 그대로 쓴다 (§14.8)."""

from __future__ import annotations

from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field

TimeHint = Literal["morning", "afternoon", "evening"]
ParseMethod = Literal["llm", "rules", "none"]


class Draft(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    date: date_type
    time_hint: TimeHint | None = None
    goal_id: int | None = None
    goal_title: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    confidence: float = Field(default=0.5, ge=0, le=1)


class ParseResult(BaseModel):
    drafts: list[Draft]
    method: ParseMethod
    warnings: list[str] = Field(default_factory=list)


class GoalHint(BaseModel):
    """LLM 과 규칙 파서가 목표 매칭에 쓰는 최소 정보."""

    goal_id: int
    title: str
    estimated_minutes: int | None = None
