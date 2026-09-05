"""3단계 폴백 오케스트레이션 (§6.1).

1) LLM (8초 타임아웃)  → method="llm"
2) 규칙 파서            → method="rules"
3) 원문 1건             → method="none"  (클라이언트는 직접 입력 폼으로 전환)
어느 경우든 200 이다. 규칙 파서 자체가 예외로 죽을 때만 503 AI_UNAVAILABLE.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from app.core.errors import AppError
from app.services.ai import llm, rules
from app.services.ai.schemas import Draft, GoalHint, ParseResult

LLM_TIMEOUT_SECONDS = 8.0
logger = logging.getLogger("p2j.ai")


async def parse(
    text: str, ref_date: date, goals: list[GoalHint], *, allow_llm: bool = True
) -> ParseResult:
    if allow_llm:
        try:
            async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                return await llm.parse(text, ref_date, goals)
        except (TimeoutError, llm.LLMUnavailable) as exc:
            # 원문은 남기지 않는다. 사유만.
            logger.info("LLM 단계 실패, 규칙 파서로 폴백: %s", exc)

    try:
        result = rules.parse(text, ref_date, goals)
    except Exception as exc:
        logger.exception("규칙 파서 예외")
        raise AppError("AI_UNAVAILABLE") from exc

    if result.drafts:
        return result

    return ParseResult(
        drafts=[Draft(title=text.strip()[:100], date=ref_date, confidence=0.0)],
        method="none",
        warnings=result.warnings,
    )
