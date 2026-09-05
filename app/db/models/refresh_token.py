"""refresh_tokens (ERD v1 §3.2 + rotation 추적 컬럼).

rotation (§1.6): /auth/refresh 마다 새 토큰을 발급하고 이전 행에 revoked_at·replaced_by 를 찍는다.
이미 revoked 된 토큰이 다시 오면 재사용 감지 → 그 사용자의 행을 전부 revoke 한다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPK


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPK,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex. 원문은 저장하지 않는다.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # rotation 으로 이 토큰을 대체한 새 토큰의 id. 재사용 감지 추적용.
    replaced_by: Mapped[int | None] = mapped_column(BigIntPK)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
