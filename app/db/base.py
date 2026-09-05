"""SQLAlchemy Declarative Base 와 공통 타입.

- 테이블·컬럼 이름은 ERD v1 (docs/specs/03-erd-v1.md) 의 snake_case 그대로.
- PK 는 BIGINT identity. SQLite(테스트)에서는 INTEGER 로 바꿔야 autoincrement 가 동작한다.
- 제약 이름은 naming_convention 으로 고정한다. Alembic autogenerate 가 이름 없는 제약을
  매번 새로 만드는 문제를 막는다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """created_at / updated_at. DB 시각(now())을 쓴다. 애플리케이션 시계에 의존하지 않는다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
