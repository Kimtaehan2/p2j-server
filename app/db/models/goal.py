"""goals (ERD v1 §3.3 + API 명세 §1.7 의 color · archived).

상태·타입은 PostgreSQL ENUM 대신 varchar + CHECK (ERD §5 의 선택지).
값 추가·삭제가 마이그레이션 한 줄로 끝난다.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPK, TimestampMixin

GOAL_TYPES = ("single", "recurring")
GOAL_STATUSES = ("active", "completed", "archived")
FREQUENCY_UNITS = ("week", "month")


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("type IN ('single', 'recurring')", name="type"),
        CheckConstraint("status IN ('active', 'completed', 'archived')", name="status"),
        CheckConstraint(
            "frequency_per IS NULL OR frequency_per IN ('week', 'month')", name="frequency_per"
        ),
        CheckConstraint(
            "type = 'single' OR (frequency_times IS NOT NULL AND frequency_per IS NOT NULL)",
            name="frequency",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="date_order"),
        Index("ix_goals_user_id_status", "user_id", "status"),
    )

    goal_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="single")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    color: Mapped[str | None] = mapped_column(String(7))
    frequency_times: Mapped[int | None] = mapped_column(SmallInteger)
    frequency_per: Mapped[str | None] = mapped_column(String(10))
    duration_weeks: Mapped[int | None] = mapped_column(SmallInteger)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    estimated_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
