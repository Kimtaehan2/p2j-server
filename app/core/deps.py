"""FastAPI Depends 모음.

보호 엔드포인트는 `Depends(get_current_user)` 하나로 통일한다 (§14.9).
인증 없는 경로는 /auth/signup, /auth/login, /auth/refresh, /health 뿐이다 (§1.6).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Unauthorized
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_session_factory

# auto_error=False: 헤더가 없을 때 FastAPI 기본 403 대신 우리 형식의 401 을 내기 위해.
bearer_scheme = HTTPBearer(auto_error=False, description="Authorization: Bearer <access_token>")


async def get_db() -> AsyncIterator[AsyncSession]:
    """요청 하나에 세션 하나. 예외 없이 끝나면 commit, 예외가 나면 rollback."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized()

    user_id = decode_access_token(credentials.credentials)

    user = await db.scalar(select(User).where(User.user_id == user_id, User.deleted_at.is_(None)))
    if user is None:
        # 탈퇴·삭제된 계정의 토큰. 재발급도 실패하도록 UNAUTHORIZED 로 통일.
        raise Unauthorized()

    # 로깅 미들웨어가 사용자 ID 를 남길 수 있게 request.state 에 둔다.
    request.state.user_id = user.user_id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
