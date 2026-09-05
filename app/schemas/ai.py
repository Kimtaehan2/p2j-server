"""/ai/* 요청 스키마 (§6)."""

from __future__ import annotations

from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, Field


class ParseContext(BaseModel):
    goal_ids: list[int] | None = None


class ParseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=500)
    reference_date: date_type | None = None
    context: ParseContext | None = None
