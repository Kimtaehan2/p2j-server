"""인증 서비스 — 토큰 발급·회전·폐기 골격 (§1.6, §14.9).

4주차에 만드는 /auth/* 엔드포인트가 이 함수들을 호출한다. 엔드포인트 파일에 로직을 쓰지 않는다.
비밀번호 검증·이메일 중복 같은 가입/로그인 규칙은 4주차에 여기에 추가한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidCredentials, Unauthorized
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.time import now_utc, service_today
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest
from app.schemas.user import user_to_dict

PASSWORD_MIN, PASSWORD_MAX = 8, 72  # 72 = bcrypt 입력 한계


def _check_password_strength(password: str) -> None:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise AppError("WEAK_PASSWORD")  # 명세 §3: details 없이


async def signup(db: AsyncSession, body: SignupRequest) -> dict[str, Any]:
    """가입 + 자동 로그인. 이메일은 소문자로 정규화한다."""
    _check_password_strength(body.password)
    email = body.email.lower()

    exists = await db.scalar(select(User.user_id).where(User.email == email))
    if exists is not None:
        raise AppError(
            "EMAIL_ALREADY_EXISTS", details={"email": "이미 가입된 이메일이에요."}
        )  # 모바일이 details.email 을 입력칸 아래에 붙인다

    user = User(email=email, password_hash=hash_password(body.password), nickname=body.nickname)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return await issue_session(db, user)


async def login(db: AsyncSession, body: LoginRequest) -> dict[str, Any]:
    """이메일 없음과 비밀번호 틀림을 구분하지 않는다 (계정 존재 여부 노출 방지)."""
    user = await db.scalar(
        select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None))
    )
    if user is None or not verify_password(body.password, user.password_hash):
        raise InvalidCredentials()
    return await issue_session(db, user)


async def issue_session(db: AsyncSession, user: User) -> dict[str, Any]:
    """로그인·가입 응답 본문(data). access + 새 refresh 행 + user(today 포함)."""
    access_token, expires_in = create_access_token(user.user_id)
    raw_refresh, token_hash, expires_at = generate_refresh_token()

    db.add(RefreshToken(user_id=user.user_id, token_hash=token_hash, expires_at=expires_at))
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "user": user_to_dict(user, service_today()),
    }


async def rotate_refresh_token(db: AsyncSession, raw_refresh: str) -> dict[str, Any]:
    """/auth/refresh 응답 본문(data).

    - 없는 토큰·만료 → 401 UNAUTHORIZED
    - 이미 revoke 된 토큰(재사용) → 그 사용자의 refresh 전부 폐기 후 401 UNAUTHORIZED
    - 정상 → 이전 행 revoke + replaced_by 기록, 새 refresh·access 발급
    """
    now = now_utc()
    row = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    if row is None:
        raise Unauthorized()

    if row.revoked_at is not None:
        # 재사용 감지. 예외를 던지면 get_db 가 rollback 하므로 폐기는 여기서 먼저 commit 한다.
        await revoke_all_for_user(db, row.user_id, now)
        await db.commit()
        raise Unauthorized()

    if _as_utc(row.expires_at) <= now:
        row.revoked_at = now
        await db.commit()
        raise Unauthorized()

    user = await db.scalar(
        select(User).where(User.user_id == row.user_id, User.deleted_at.is_(None))
    )
    if user is None:
        raise Unauthorized()

    access_token, expires_in = create_access_token(user.user_id, now=now)
    new_raw, new_hash, new_expires_at = generate_refresh_token()
    new_row = RefreshToken(user_id=user.user_id, token_hash=new_hash, expires_at=new_expires_at)
    db.add(new_row)
    await db.flush()

    row.revoked_at = now
    row.replaced_by = new_row.token_id
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": new_raw,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


async def revoke_refresh_token(db: AsyncSession, raw_refresh: str | None) -> None:
    """/auth/logout. 이미 무효여도 조용히 넘어간다 (멱등, §3)."""
    if not raw_refresh:
        return
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw_refresh),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now_utc())
    )


async def revoke_all_for_user(db: AsyncSession, user_id: int, now: datetime | None = None) -> None:
    """재사용 감지·비밀번호 변경·탈퇴 시 세션 전체 무효화."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now or now_utc())
    )


def _as_utc(value: datetime) -> datetime:
    # SQLite 는 tz 정보를 잃고 naive 로 돌려준다. UTC 로 저장했으므로 그대로 붙인다.
    from datetime import UTC

    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
