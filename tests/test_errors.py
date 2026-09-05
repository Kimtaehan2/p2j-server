"""오류 응답 형식 (§1.2·§1.3). 모바일 ApiException 이 파싱하는 형태 그대로여야 한다."""

from typing import Annotated

import pytest
from fastapi import APIRouter, FastAPI, Query
from httpx import AsyncClient
from pydantic import BaseModel, Field

from app.core.errors import ERROR_CATALOG, AppError, DeclaredTodoLocked, TodoNotFound
from app.core.response import decode_cursor, encode_cursor, ok, paged


class _Item(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


class _Bulk(BaseModel):
    items: list[_Item] = Field(min_length=1, max_length=20)


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    """검증·예외 경로를 자극하기 위한 테스트 전용 라우트."""
    router = APIRouter(prefix="/_test")

    @router.post("/validate")
    async def validate(body: _Item) -> dict:
        return ok(body.model_dump())

    @router.post("/bulk")
    async def bulk(body: _Bulk) -> dict:
        return ok({"created_count": len(body.items)})

    @router.get("/query")
    async def query(limit: Annotated[int, Query(ge=1, le=50)]) -> dict:
        return ok({"limit": limit})

    @router.get("/locked")
    async def locked() -> dict:
        raise DeclaredTodoLocked()

    @router.get("/todo-missing")
    async def todo_missing() -> dict:
        raise TodoNotFound()

    @router.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("DATABASE_URL=postgresql://secret")  # 응답에 새면 안 된다

    @router.get("/paged")
    async def paged_route() -> dict:
        return paged([1, 2], next_cursor=encode_cursor({"id": 2}))

    app.include_router(router, prefix="/v1")
    return app


async def test_catalog_has_every_spec_code() -> None:
    # 명세 §1.4 의 코드가 빠지면 서비스 코드에서 AppError 생성 자체가 실패한다.
    spec_codes = {
        "VALIDATION_ERROR", "WEAK_PASSWORD", "INVALID_CREDENTIALS", "TOKEN_EXPIRED",
        "UNAUTHORIZED", "FORBIDDEN", "NOT_GROUP_MEMBER", "NOT_GROUP_ADMIN", "NOT_FOUND",
        "TODO_NOT_FOUND", "GOAL_NOT_FOUND", "GROUP_NOT_FOUND", "DECLARATION_NOT_FOUND",
        "USER_NOT_FOUND", "EMAIL_ALREADY_EXISTS", "ALREADY_MEMBER",
        "DECLARATION_ALREADY_EXISTS", "TODO_ALREADY_DONE", "TODO_NOT_DONE", "FILE_TOO_LARGE",
        "UNSUPPORTED_FILE_TYPE", "DECLARED_TODO_LOCKED", "DECLARATION_CLOSED",
        "DECLARATION_EMPTY", "GROUP_FULL", "INVALID_INVITE_CODE", "INVITE_CODE_EXPIRED",
        "ADMIN_MUST_TRANSFER", "CANNOT_KICK_SELF", "AI_QUOTA_EXCEEDED", "RATE_LIMITED",
        "INTERNAL_ERROR", "AI_UNAVAILABLE", "STORAGE_UNAVAILABLE",
    }  # fmt: skip
    assert spec_codes <= set(ERROR_CATALOG)
    for code, (status, message) in ERROR_CATALOG.items():
        assert 400 <= status < 600, code
        assert message and not message.isascii(), f"{code}: 메시지는 한국어여야 한다"


def test_unknown_code_is_rejected_early() -> None:
    with pytest.raises(ValueError):
        AppError("NOT_IN_CATALOG")


async def test_app_error_shape(client: AsyncClient) -> None:
    r = await client.get("/v1/_test/locked")
    assert r.status_code == 422
    assert r.json() == {
        "error": {
            "code": "DECLARED_TODO_LOCKED",
            "message": "그룹에 선언한 항목은 오늘 수정할 수 없어요.",
            "details": {},
        }
    }
    assert "X-Request-Id" in r.headers

    r = await client.get("/v1/_test/todo-missing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TODO_NOT_FOUND"


async def test_validation_error_is_400_with_korean_field_messages(client: AsyncClient) -> None:
    r = await client.post("/v1/_test/validate", json={"title": "", "estimated_minutes": 0})
    assert r.status_code == 400  # FastAPI 기본 422 가 아니다
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "입력값을 확인해 주세요."
    assert body["error"]["details"] == {
        "title": "1자 이상 입력해 주세요.",
        "estimated_minutes": "1 이상이어야 해요.",
    }
    assert "detail" not in body


async def test_validation_missing_field(client: AsyncClient) -> None:
    r = await client.post("/v1/_test/validate", json={})
    assert r.status_code == 400
    assert r.json()["error"]["details"] == {"title": "필수 항목이에요."}


async def test_validation_nested_list_uses_bracket_path(client: AsyncClient) -> None:
    # §5 /todos/bulk: details 키는 items[1].title 형태
    r = await client.post("/v1/_test/bulk", json={"items": [{"title": "ok"}, {"title": ""}]})
    assert r.status_code == 400
    assert r.json()["error"]["details"] == {"items[1].title": "1자 이상 입력해 주세요."}


async def test_validation_invalid_json_body(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/_test/validate", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.json()["error"]["details"]["body"] == "요청 본문이 올바른 JSON 이 아니에요."


async def test_query_param_validation(client: AsyncClient) -> None:
    r = await client.get("/v1/_test/query", params={"limit": 999})
    assert r.status_code == 400
    assert r.json()["error"]["details"] == {"limit": "50 이하여야 해요."}


async def test_unknown_route_is_json_404(client: AsyncClient) -> None:
    r = await client.get("/v1/no-such-path")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["details"] == {"method": "GET", "path": "/v1/no-such-path"}


async def test_method_not_allowed_is_json(client: AsyncClient) -> None:
    r = await client.delete("/v1/health")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


async def test_unhandled_exception_is_500_without_leaking(client: AsyncClient) -> None:
    r = await client.get("/v1/_test/boom")
    assert r.status_code == 500
    assert r.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
            "details": {},
        }
    }
    assert "secret" not in r.text


async def test_request_id_is_echoed(client: AsyncClient) -> None:
    r = await client.get("/v1/_test/paged", headers={"X-Request-Id": "abc-123"})
    assert r.headers["X-Request-Id"] == "abc-123"


async def test_paged_wrapper(client: AsyncClient) -> None:
    body = (await client.get("/v1/_test/paged")).json()
    assert body["data"] == [1, 2]
    assert body["page"]["has_next"] is True
    assert decode_cursor(body["page"]["next_cursor"]) == {"id": 2}
    assert paged([], None)["page"] == {"next_cursor": None, "has_next": False}


def test_cursor_round_trip_and_rejection() -> None:
    cursor = encode_cursor({"id": 123, "at": "2026-09-05T08:00:00+09:00"})
    assert "=" not in cursor
    assert decode_cursor(cursor) == {"id": 123, "at": "2026-09-05T08:00:00+09:00"}
    assert decode_cursor(None) is None
    with pytest.raises(AppError) as info:
        decode_cursor("!!!not-base64!!!")
    assert info.value.code == "VALIDATION_ERROR"
    assert "cursor" in info.value.details
