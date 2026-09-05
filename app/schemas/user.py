"""User 응답 직렬화 (API 명세 v1 §1.7).

응답 스키마는 dict 를 만드는 함수로 둔다 (§14.4). 필드명은 snake_case 그대로 (§14.5).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.time import to_kst_iso
from app.db.models.user import User


def user_to_dict(user: User, today: date) -> dict[str, Any]:
    """`today` 는 GET /auth/me 와 로그인·가입 응답의 user 에 반드시 포함한다."""
    return {
        "user_id": user.user_id,
        "nickname": user.nickname,
        "profile_image_url": user.profile_image_url,
        "created_at": to_kst_iso(user.created_at),
        "today": today.isoformat(),
    }


def public_user_to_dict(user: User | None, *, user_id: int | None = None) -> dict[str, Any]:
    """그룹 피드·구성원 목록에서 타인을 나타낼 때. 이메일·today·created_at 은 내보내지 않는다."""
    if user is None or user.deleted_at is not None:
        return {
            "user_id": user.user_id if user else user_id,
            "nickname": "탈퇴한 사용자",
            "profile_image_url": None,
        }
    return {
        "user_id": user.user_id,
        "nickname": user.nickname,
        "profile_image_url": user.profile_image_url,
    }
