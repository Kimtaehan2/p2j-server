"""1단계 — GPT-4o-mini 구조화 출력 (§6.1, §14.8).

Pydantic 모델(DraftList)을 response_format 으로 넘겨 JSON schema 를 따로 쓰지 않는다.
API 키가 없으면 LLMUnavailable 을 던지고 파이프라인이 규칙 파서로 내려간다.
입력 원문은 로그에 남기지 않는다 (§11).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.ai.schemas import Draft, GoalHint, ParseResult, TimeHint


class LLMUnavailable(Exception):
    """키 없음 · 네트워크 · 스키마 위반 등 LLM 단계에서 결과를 못 얻은 모든 경우."""


class _LLMDraft(BaseModel):
    title: str = Field(description="할 일 제목. 날짜·시간 표현은 뺀 동사형 짧은 문장")
    date: str = Field(description="YYYY-MM-DD. 상대 날짜는 기준일로 환산")
    time_hint: TimeHint | None = Field(default=None, description="아침/오후/저녁 언급 시")
    goal_id: int | None = Field(
        default=None, description="주어진 목표 목록 중 관련 목표. 없으면 null"
    )
    estimated_minutes: int | None = Field(
        default=None, description="언급된 소요 시간(분). 없으면 null"
    )
    confidence: float = Field(ge=0, le=1)


class DraftList(BaseModel):
    drafts: list[_LLMDraft]
    warnings: list[Literal["date_ambiguous", "date_in_past"]] = Field(default_factory=list)


SYSTEM_PROMPT = """너는 한국어 할 일 정리 도우미다. 사용자가 말한 문장을 개별 할 일로 쪼갠다.
규칙:
- 하나의 행동 = 하나의 할 일. 접속사("그리고", "하고")로 이어진 것은 나눈다.
- date 는 기준일({today}, {weekday}) 기준으로 환산한다.
  "내일"=+1, "모레"=+2, "다음 주 X요일"=다음 주.
  날짜 언급이 없으면 기준일. 앞 문장의 날짜를 뒤 문장이 물려받는다.
- 과거 날짜로 해석되면 기준일로 두고 warnings 에 "date_in_past" 를 넣는다.
- goal_id 는 아래 목표 목록에서 분명히 관련된 것만. 확신이 없으면 null.
- estimated_minutes 는 명시적으로 말한 경우만. 추측하지 않는다.
- 제목은 30자 이내의 자연스러운 한국어. 날짜·시간대 표현은 제목에서 뺀다.
목표 목록:
{goals}"""

WEEKDAY_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def _goal_lines(goals: list[GoalHint]) -> str:
    if not goals:
        return "(없음)"
    return "\n".join(f"- goal_id={g.goal_id}: {g.title}" for g in goals)


async def parse(text: str, ref_date: date, goals: list[GoalHint]) -> ParseResult:
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMUnavailable("OPENAI_API_KEY 없음")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        completion = await client.beta.chat.completions.parse(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(
                        today=ref_date.isoformat(),
                        weekday=WEEKDAY_KO[ref_date.weekday()],
                        goals=_goal_lines(goals),
                    ),
                },
                {"role": "user", "content": text},
            ],
            response_format=DraftList,
            temperature=0.2,
        )
        parsed = completion.choices[0].message.parsed
    except Exception as exc:  # noqa: BLE001 — 어떤 실패든 폴백 대상
        raise LLMUnavailable(type(exc).__name__) from exc

    if parsed is None or not parsed.drafts:
        raise LLMUnavailable("빈 결과")

    goal_by_id = {g.goal_id: g for g in goals}
    warnings = set(parsed.warnings)
    drafts: list[Draft] = []
    for item in parsed.drafts:
        try:
            day = date.fromisoformat(item.date)
        except ValueError:
            day = ref_date
            warnings.add("date_ambiguous")
        if day < ref_date:
            day = ref_date
            warnings.add("date_in_past")
        goal = goal_by_id.get(item.goal_id) if item.goal_id is not None else None
        drafts.append(
            Draft(
                title=item.title.strip()[:100] or text[:100],
                date=day,
                time_hint=item.time_hint,
                goal_id=goal.goal_id if goal else None,  # 목록에 없는 id 는 버린다
                goal_title=goal.title if goal else None,
                estimated_minutes=item.estimated_minutes
                if item.estimated_minutes and 1 <= item.estimated_minutes <= 1440
                else None,
                confidence=item.confidence,
            )
        )
    return ParseResult(drafts=drafts, method="llm", warnings=sorted(warnings))
