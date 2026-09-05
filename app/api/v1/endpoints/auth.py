"""/auth/* — 3주차 골격.

이번 범위에서는 보호 엔드포인트 하나(`GET /auth/me`)만 두어 JWT 체인
(Bearer 헤더 → 토큰 검증 → DB 사용자 조회 → today 포함 응답)이 끝까지 동작하는지 확인한다.
signup / login / refresh / logout 은 4주차에 services/auth.py 의 함수를 호출하는 형태로 추가한다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.core.response import ok
from app.core.time import service_today
from app.schemas.user import user_to_dict

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    summary="내 정보 + 서버 기준 today",
    description="모바일이 앱 복귀마다 호출한다. DB 1회 조회 이내로 유지한다.",
)
async def me(user: CurrentUser) -> dict[str, Any]:
    return ok(user_to_dict(user, service_today()))
