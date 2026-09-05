"""04:00 KST 하루 경계 (BR-01). 모바일 MockStore.serverToday() 와 같은 결과여야 한다."""

from datetime import UTC, date, datetime

import pytest

from app.core.time import (
    KST,
    service_day_range,
    service_day_start,
    service_today,
    to_kst_iso,
    week_range,
)


def kst(y: int, m: int, d: int, hh: int, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=KST)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (kst(2026, 9, 4, 3, 59), date(2026, 9, 3)),  # 03:59 는 전날
        (kst(2026, 9, 4, 4, 0), date(2026, 9, 4)),  # 04:00 은 당일
        (kst(2026, 9, 4, 0, 0), date(2026, 9, 3)),  # 자정은 전날
        (kst(2026, 9, 4, 23, 59), date(2026, 9, 4)),
        (kst(2026, 10, 1, 3, 0), date(2026, 9, 30)),  # 월말
        (kst(2028, 3, 1, 3, 0), date(2028, 2, 29)),  # 윤년
        (kst(2027, 1, 1, 3, 0), date(2026, 12, 31)),  # 연말
        (kst(2027, 1, 1, 4, 0), date(2027, 1, 1)),
    ],
)
def test_service_today(now: datetime, expected: date) -> None:
    assert service_today(now) == expected


def test_service_today_is_timezone_independent() -> None:
    # 같은 절대 시각을 UTC 로 표현해도 결과가 같다 (Railway 는 UTC 컨테이너).
    instant_utc = datetime(2026, 9, 3, 18, 59, tzinfo=UTC)  # = 09-04 03:59 KST
    assert service_today(instant_utc) == date(2026, 9, 3)
    naive = datetime(2026, 9, 3, 18, 59)  # naive 는 UTC 로 본다
    assert service_today(naive) == date(2026, 9, 3)


def test_custom_start_hour() -> None:
    assert service_today(kst(2026, 9, 4, 3, 59), day_start_hour=0) == date(2026, 9, 4)


def test_service_day_start_round_trips() -> None:
    start = service_day_start(date(2026, 9, 4))
    assert start.isoformat() == "2026-09-04T04:00:00+09:00"
    assert service_today(start) == date(2026, 9, 4)
    lo, hi = service_day_range(date(2026, 9, 4))
    assert (hi - lo).days == 1


def test_week_range_is_monday_to_sunday() -> None:
    assert week_range(date(2026, 9, 5)) == (date(2026, 8, 31), date(2026, 9, 6))  # 토요일
    assert week_range(date(2026, 8, 31)) == (date(2026, 8, 31), date(2026, 9, 6))  # 월요일


def test_to_kst_iso_always_uses_plus_nine() -> None:
    assert to_kst_iso(datetime(2026, 9, 5, 5, 30, tzinfo=UTC)) == "2026-09-05T14:30:00+09:00"
    assert to_kst_iso(datetime(2026, 9, 5, 5, 30)) == "2026-09-05T14:30:00+09:00"
    assert to_kst_iso(None) is None
