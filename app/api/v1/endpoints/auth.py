"""/auth/* (API 명세 §3). 로직은 services/auth.py.

signup/login/refresh 는 인증 없는 경로다 (§1.6). 모바일도 이 경로엔 헤더를 붙이지 않는다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, DbSession
from app.core.response import no_content, ok
from app.core.time import service_today
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, SignupRequest
from app.schemas.user import user_to_dict
from app.services import auth as svc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", summary="가입 + 자동 로그인")
async def signup(db: DbSession, body: SignupRequest) -> dict[str, Any]:
    # 명세 §3: 201 이 아니라 200 으로 통일
    return ok(await svc.signup(db, body))


@router.post("/login", summary="로그인")
async def login(db: DbSession, body: LoginRequest) -> dict[str, Any]:
    return ok(await svc.login(db, body))


@router.post("/refresh", summary="토큰 재발급 (rotation)")
async def refresh(db: DbSession, body: RefreshRequest) -> dict[str, Any]:
    return ok(await svc.rotate_refresh_token(db, body.refresh_token))


@router.post("/logout", status_code=204, summary="refresh 무효화 (멱등)")
async def logout(user: CurrentUser, db: DbSession, body: LogoutRequest | None = None) -> Response:
    await svc.revoke_refresh_token(db, body.refresh_token if body else None)
    return no_content()


@router.get(
    "/me",
    summary="내 정보 + 서버 기준 today",
    description="모바일이 앱 복귀마다 호출한다. DB 1회 조회 이내로 유지한다.",
)
async def me(user: CurrentUser) -> dict[str, Any]:
    return ok(user_to_dict(user, service_today()))
