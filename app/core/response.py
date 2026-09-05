"""성공 응답 래퍼와 커서 유틸 (API 명세 v1 §1.2·§1.5).

엔드포인트는 dict 를 그대로 반환하고 `response_model` 을 쓰지 않는다.
제네릭 Envelope 스키마는 학기 프로젝트에서 타입 오류로 시간을 잡아먹는다(§14.4).

    return ok(todo_dict)                       # { "data": {...} }
    return paged(items, next_cursor=cursor)    # { "data": [...], "page": {...} }
    return no_content()                        # 204. 감싸지 않는다.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import Response

from app.core.errors import AppError

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 50


def ok(data: Any) -> dict[str, Any]:
    return {"data": data}


def paged(items: list[Any], next_cursor: str | None = None) -> dict[str, Any]:
    return {
        "data": items,
        "page": {"next_cursor": next_cursor, "has_next": next_cursor is not None},
    }


def no_content() -> Response:
    """204. 모바일 uncomplete 가 본문 없음을 전제로 summary 를 재계산한다."""
    return Response(status_code=204)


def encode_cursor(payload: dict[str, Any]) -> str:
    """서버만 해석하는 불투명 커서. base64url(JSON), 패딩 제거."""
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=str)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError(
            "VALIDATION_ERROR",
            details={"cursor": "잘못된 페이지 정보예요. 처음부터 다시 불러 주세요."},
        ) from exc
    if not isinstance(data, dict):
        raise AppError("VALIDATION_ERROR", details={"cursor": "잘못된 페이지 정보예요."})
    return data


def clamp_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return DEFAULT_PAGE_LIMIT
    return min(limit, MAX_PAGE_LIMIT)
