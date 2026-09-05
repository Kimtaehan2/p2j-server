"""AI 호출 쿼터 (§6 GET /ai/quota, BR-09).

- 일 한도(기본 30): 초과해도 429 가 아니라 규칙 파서로 폴백 + warnings=["quota_exceeded"].
- 분 한도(5): 초과 시 429 AI_QUOTA_EXCEEDED.
- 저장소는 Redis. 일 카운터 키는 서비스 날짜(04:00 경계)로 끊고 다음 경계 시각에 만료한다.
- Redis 가 내려가 있으면 카운트를 건너뛴다 (AI 가 막히는 것보다 낫다). 로그만 남긴다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from app.core.config import get_settings
from app.core.time import now_utc, service_day_start, service_today, to_kst_iso
from app.db.redis import get_redis

PER_MINUTE_LIMIT = 5
logger = logging.getLogger("p2j.ai")


@dataclass
class QuotaState:
    limit_per_day: int
    used_today: int
    reset_at: str  # ISO KST

    @property
    def remaining_today(self) -> int:
        return max(self.limit_per_day - self.used_today, 0)

    def to_dict(self) -> dict[str, int | str]:
        return {
            "limit_per_day": self.limit_per_day,
            "used_today": self.used_today,
            "remaining_today": self.remaining_today,
            "reset_at": self.reset_at,
        }


def _reset_at() -> str:
    return to_kst_iso(service_day_start(service_today() + timedelta(days=1))) or ""


def _day_key(user_id: int) -> str:
    return f"ai:quota:day:{service_today().isoformat()}:{user_id}"


def _minute_key(user_id: int) -> str:
    return f"ai:quota:min:{now_utc().strftime('%Y%m%d%H%M')}:{user_id}"


async def get_state(user_id: int) -> QuotaState:
    limit = get_settings().ai_parse_daily_limit
    try:
        used = int(await get_redis().get(_day_key(user_id)) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 쿼터 조회 실패, 0 으로 간주: %s", type(exc).__name__)
        used = 0
    return QuotaState(limit_per_day=limit, used_today=used, reset_at=_reset_at())


async def consume(user_id: int) -> tuple[QuotaState, bool, bool]:
    """(현재 상태, 분 한도 초과 여부, 일 한도 초과 여부). 호출 1회를 소비한다."""
    limit = get_settings().ai_parse_daily_limit
    try:
        redis = get_redis()
        pipe = redis.pipeline()
        pipe.incr(_minute_key(user_id))
        pipe.expire(_minute_key(user_id), 120)
        pipe.incr(_day_key(user_id))
        pipe.expireat(
            _day_key(user_id),
            int(service_day_start(service_today() + timedelta(days=1)).timestamp()),
        )
        minute_count, _, day_count, _ = await pipe.execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 쿼터 갱신 실패, 무제한으로 진행: %s", type(exc).__name__)
        return QuotaState(limit, 0, _reset_at()), False, False

    state = QuotaState(limit_per_day=limit, used_today=int(day_count), reset_at=_reset_at())
    return state, int(minute_count) > PER_MINUTE_LIMIT, int(day_count) > limit
