"""todos (ERD v1 §3.4 `todo_items` → API 명세 테이블 목록의 `todos`).

- `declared_at` 이 NULL 이 아니면 선언 잠금 (ERD §2.3). `is_declared` 는 이 값으로 계산.
- `postpone_count` 는 ERD 의 `deferred_from` 대신 (pending A-6 (a)안). 미룬 횟수만 센다.
- `display_order` 는 API 의 `order`. 파이썬 예약어 충돌을 피한다.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK, TimestampMixin
from app.db.models.goal import Goal

TODO_STATUSES = ("pending", "done", "deferred", "skipped")
TODO_SOURCES = ("manual", "ai_suggested", "auto_scheduled")


class Todo(TimestampMixin, Base):
    __tablename__ = "todos"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'done', 'deferred', 'skipped')", name="status"),
        CheckConstraint("source IN ('manual', 'ai_suggested', 'auto_scheduled')", name="source"),
        # 가장 빈번한 쿼리: 하루 목록. soft delete 된 행은 제외 (ERD §4)
        Index(
            "ix_todos_user_id_date_alive",
            "user_id",
            "date",
            postgresql_where="deleted_at IS NULL",
        ),
        # 목표별 진행률 집계
        Index("ix_todos_goal_id_status", "goal_id", "status"),
    )

    todo_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("goals.goal_id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    estimated_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    actual_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    postpone_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    memo: Mapped[str | None] = mapped_column(String(500))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    goal: Mapped[Goal | None] = relationship(Goal, lazy="joined")

    @property
    def is_declared(self) -> bool:
        return self.declared_at is not None
