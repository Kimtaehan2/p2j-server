"""JWT 골격: 비밀번호 해시, access 토큰, Bearer 가드, refresh rotation."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.services.auth import (
    issue_session,
    revoke_refresh_token,
    rotate_refresh_token,
)

# ---- security -------------------------------------------------------------------


def test_password_hash_round_trip() -> None:
    hashed = hash_password("password123")
    assert hashed.startswith("$2b$12$")
    assert verify_password("password123", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("password123", "not-a-hash")


def test_access_token_round_trip() -> None:
    token, expires_in = create_access_token(42)
    assert expires_in == get_settings().jwt_access_ttl_seconds == 1800
    assert decode_access_token(token) == 42


def test_expired_access_token_is_token_expired() -> None:
    token, _ = create_access_token(1, now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(AppError) as info:
        decode_access_token(token)
    assert info.value.code == "TOKEN_EXPIRED"
    assert info.value.status == 401


def test_tampered_or_foreign_token_is_unauthorized() -> None:
    settings = get_settings()
    forged = jwt.encode(
        {"sub": "1", "type": "access", "exp": 4102444800},
        "other-secret-other-secret-other-secret-32",
        algorithm="HS256",
    )
    wrong_type = jwt.encode(
        {"sub": "1", "type": "refresh", "exp": 4102444800},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    for token in (forged, wrong_type, "garbage"):
        with pytest.raises(AppError) as info:
            decode_access_token(token)
        assert info.value.code == "UNAUTHORIZED"


# ---- GET /auth/me 가드 -----------------------------------------------------------


async def test_me_without_token_is_401_unauthorized(client: AsyncClient) -> None:
    r = await client.get("/v1/auth/me")
    assert r.status_code == 401  # FastAPI HTTPBearer 기본 403 이 아니다
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_with_expired_token_is_token_expired(client: AsyncClient, user: User) -> None:
    token, _ = create_access_token(user.user_id, now=datetime.now(UTC) - timedelta(hours=1))
    r = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_me_returns_user_with_today(
    client: AsyncClient, user: User, auth_headers: dict[str, str]
) -> None:
    r = await client.get("/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user_id"] == user.user_id
    assert data["nickname"] == "태한"
    assert data["profile_image_url"] is None
    assert data["created_at"].endswith("+09:00")
    assert len(data["today"]) == 10  # YYYY-MM-DD
    assert "email" not in data and "password_hash" not in data


async def test_me_for_deleted_user_is_unauthorized(
    client: AsyncClient, db: AsyncSession, user: User, auth_headers: dict[str, str]
) -> None:
    user.deleted_at = datetime.now(UTC)
    await db.commit()
    r = await client.get("/v1/auth/me", headers=auth_headers)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


# ---- refresh rotation (services/auth.py) -----------------------------------------


async def test_issue_session_shape(db: AsyncSession, user: User) -> None:
    session = await issue_session(db, user)
    await db.commit()
    assert set(session) == {"access_token", "refresh_token", "token_type", "expires_in", "user"}
    assert session["token_type"] == "Bearer"
    assert session["expires_in"] == 1800
    assert session["user"]["user_id"] == user.user_id
    assert "today" in session["user"]
    rows = (await db.scalars(select(RefreshToken))).all()
    assert len(rows) == 1
    assert rows[0].token_hash != session["refresh_token"]  # 원문을 저장하지 않는다


async def test_refresh_rotation_and_reuse_detection(db: AsyncSession, user: User) -> None:
    first = await issue_session(db, user)
    await db.commit()

    rotated = await rotate_refresh_token(db, first["refresh_token"])
    await db.commit()
    assert rotated["refresh_token"] != first["refresh_token"]
    assert decode_access_token(rotated["access_token"]) == user.user_id

    rows = (await db.scalars(select(RefreshToken).order_by(RefreshToken.token_id))).all()
    assert rows[0].revoked_at is not None
    assert rows[0].replaced_by == rows[1].token_id
    assert rows[1].revoked_at is None

    # 이전 refresh 재사용 → 세션 전체 폐기 + 401 UNAUTHORIZED
    with pytest.raises(AppError) as info:
        await rotate_refresh_token(db, first["refresh_token"])
    await db.commit()
    assert info.value.code == "UNAUTHORIZED"
    for row in (await db.scalars(select(RefreshToken))).all():
        await db.refresh(row)
        assert row.revoked_at is not None

    # 새 토큰도 이제 무효
    with pytest.raises(AppError):
        await rotate_refresh_token(db, rotated["refresh_token"])


async def test_refresh_unknown_and_expired(db: AsyncSession, user: User) -> None:
    with pytest.raises(AppError) as info:
        await rotate_refresh_token(db, "never-issued")
    assert info.value.code == "UNAUTHORIZED"

    session = await issue_session(db, user)
    row = await db.scalar(select(RefreshToken))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    with pytest.raises(AppError):
        await rotate_refresh_token(db, session["refresh_token"])


async def test_logout_is_idempotent(db: AsyncSession, user: User) -> None:
    session = await issue_session(db, user)
    await db.commit()
    await revoke_refresh_token(db, session["refresh_token"])
    await revoke_refresh_token(db, session["refresh_token"])  # 두 번째도 예외 없음
    await revoke_refresh_token(db, None)
    await db.commit()
    row = await db.scalar(select(RefreshToken))
    assert row is not None and row.revoked_at is not None
