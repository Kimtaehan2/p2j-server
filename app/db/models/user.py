"""users (ERD v1 §3.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPK, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("day_start_hour BETWEEN 0 AND 23", name="day_start_hour"),)

    user_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(30), nullable=False)
    profile_image_url: Mapped[str | None] = mapped_column(String(500))
    # 하루 경계. 명세는 전역 04:00 고정이지만 ERD 컬럼은 남긴다 (pending A-2).
    day_start_hour: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=4, server_default="4"
    )
    # soft delete. 30일 뒤 배치가 완전 삭제한다 (BR-14).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # 이메일은 로그에 남기지 않는다.
        return f"<User id={self.user_id}>"
