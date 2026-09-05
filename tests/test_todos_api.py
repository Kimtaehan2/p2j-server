"""/todos/* — 모바일 TodoApi 가 호출하는 계약 + 명세 §5 규칙."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.core.time import service_today
from app.db.models import Goal, Todo, User


@pytest.fixture
async def goal(db: AsyncSession, user: User) -> Goal:
    g = Goal(
        user_id=user.user_id,
        title="주 3회 운동하기",
        type="recurring",
        frequency_times=3,
        frequency_per="week",
        duration_weeks=4,
        start_date=service_today(),
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return g


async def _create(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    payload = {"title": "백준 실버 2문제", "estimated_minutes": 45, **overrides}
    r = await client.post("/v1/todos", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def test_create_defaults(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    todo = await _create(client, auth_headers)
    assert todo["date"] == service_today().isoformat()
    assert todo["status"] == "pending"
    assert todo["source"] == "manual"
    assert todo["order"] == 1
    assert todo["is_declared"] is False
    assert todo["postpone_count"] == 0
    assert todo["proof"] is None
    assert todo["goal_id"] is None and todo["goal_title"] is None

    second = await _create(client, auth_headers, title="두 번째")
    assert second["order"] == 2


async def test_create_with_goal_joins_title(
    client: AsyncClient, auth_headers: dict[str, str], goal: Goal
) -> None:
    todo = await _create(client, auth_headers, goal_id=goal.goal_id)
    assert todo["goal_id"] == goal.goal_id
    assert todo["goal_title"] == "주 3회 운동하기"


async def test_create_rejects_foreign_or_archived_goal(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession, goal: Goal
) -> None:
    r = await client.post("/v1/todos", json={"title": "x", "goal_id": 999999}, headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "GOAL_NOT_FOUND"

    goal.status = "archived"
    await db.commit()
    r = await client.post(
        "/v1/todos", json={"title": "x", "goal_id": goal.goal_id}, headers=auth_headers
    )
    assert r.status_code == 400
    assert "goal_id" in r.json()["error"]["details"]


async def test_create_validation_and_date_range(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/todos", json={"title": "   ", "estimated_minutes": 0}, headers=auth_headers
    )
    assert r.status_code == 400
    assert set(r.json()["error"]["details"]) == {"title", "estimated_minutes"}

    far = (service_today() + timedelta(days=400)).isoformat()
    r = await client.post("/v1/todos", json={"title": "x", "date": far}, headers=auth_headers)
    assert r.status_code == 400
    assert "date" in r.json()["error"]["details"]


async def test_list_day_and_summary(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    a = await _create(client, auth_headers, title="A", estimated_minutes=60)
    await _create(client, auth_headers, title="B", estimated_minutes=80)
    await client.post(f"/v1/todos/{a['todo_id']}/complete", json={}, headers=auth_headers)

    r = await client.get("/v1/todos", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["date"] == service_today().isoformat()
    assert [t["title"] for t in data["items"]] == ["A", "B"]
    assert data["summary"] == {
        "total": 2,
        "done": 1,
        "achievement_rate": 0.5,
        "total_estimated_minutes": 140,
    }
    assert data["declaration"] is None

    empty = await client.get("/v1/todos", params={"date": "2000-01-01"}, headers=auth_headers)
    assert empty.json()["data"]["summary"]["total"] == 0


async def test_week_strip_is_seven_days(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _create(client, auth_headers)
    r = await client.get("/v1/todos/week", headers=auth_headers)
    assert r.status_code == 200
    days = r.json()["data"]
    assert len(days) == 7
    assert days[-1]["date"] == service_today().isoformat()
    assert days[-1]["total"] == 1 and days[0]["total"] == 0
    assert "page" not in r.json()


async def test_get_patch_delete(
    client: AsyncClient, auth_headers: dict[str, str], goal: Goal
) -> None:
    todo = await _create(client, auth_headers)
    tid = todo["todo_id"]

    r = await client.get(f"/v1/todos/{tid}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["data"]["todo_id"] == tid

    r = await client.patch(
        f"/v1/todos/{tid}",
        json={"title": "고침", "memo": "메모", "goal_id": goal.goal_id},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["title"] == "고침" and body["memo"] == "메모" and body["goal_title"] == goal.title

    # goal_id 를 null 로 명시하면 떼어낸다
    r = await client.patch(f"/v1/todos/{tid}", json={"goal_id": None}, headers=auth_headers)
    assert r.json()["data"]["goal_id"] is None

    r = await client.delete(f"/v1/todos/{tid}", headers=auth_headers)
    assert r.status_code == 204 and r.content == b""
    r = await client.get(f"/v1/todos/{tid}", headers=auth_headers)
    assert r.status_code == 404 and r.json()["error"]["code"] == "TODO_NOT_FOUND"


async def test_patch_date_forward_counts_as_postpone(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    todo = await _create(client, auth_headers)
    tomorrow = (service_today() + timedelta(days=1)).isoformat()
    r = await client.patch(
        f"/v1/todos/{todo['todo_id']}", json={"date": tomorrow}, headers=auth_headers
    )
    assert r.json()["data"]["postpone_count"] == 1
    yesterday = (service_today() - timedelta(days=1)).isoformat()
    r = await client.patch(
        f"/v1/todos/{todo['todo_id']}", json={"date": yesterday}, headers=auth_headers
    )
    assert r.json()["data"]["postpone_count"] == 1  # 과거로는 증가 없음


async def test_other_users_todo_is_hidden_as_404(
    client: AsyncClient, db: AsyncSession, user: User, auth_headers: dict[str, str]
) -> None:
    other = User(email="other@p2j.dev", password_hash=hash_password("password123"), nickname="영준")
    db.add(other)
    await db.commit()
    other_token, _ = create_access_token(other.user_id)
    todo = await _create(client, {"Authorization": f"Bearer {other_token}"})

    for method, path in (
        ("get", f"/v1/todos/{todo['todo_id']}"),
        ("delete", f"/v1/todos/{todo['todo_id']}"),
    ):
        r = await getattr(client, method)(path, headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "TODO_NOT_FOUND"


async def test_declared_todo_is_locked(
    client: AsyncClient, db: AsyncSession, auth_headers: dict[str, str]
) -> None:
    todo = await _create(client, auth_headers)
    row = await db.get(Todo, todo["todo_id"])
    assert row is not None
    row.declared_at = datetime.now(UTC)
    await db.commit()

    r = await client.patch(
        f"/v1/todos/{todo['todo_id']}", json={"title": "바꿈"}, headers=auth_headers
    )
    assert r.status_code == 422
    assert r.json()["error"] == {
        "code": "DECLARED_TODO_LOCKED",
        "message": "그룹에 선언한 항목은 오늘 수정할 수 없어요.",
        "details": {},
    }
    assert (
        await client.delete(f"/v1/todos/{todo['todo_id']}", headers=auth_headers)
    ).status_code == 422
    # memo·estimated_minutes·order 와 완료는 허용
    r = await client.patch(
        f"/v1/todos/{todo['todo_id']}",
        json={"memo": "ok", "estimated_minutes": 10},
        headers=auth_headers,
    )
    assert r.status_code == 200
    r = await client.post(f"/v1/todos/{todo['todo_id']}/complete", json={}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["data"]["todo"]["is_declared"] is True


async def test_complete_uncomplete(
    client: AsyncClient, auth_headers: dict[str, str], goal: Goal
) -> None:
    todo = await _create(client, auth_headers, goal_id=goal.goal_id, estimated_minutes=60)
    tid = todo["todo_id"]

    r = await client.post(
        f"/v1/todos/{tid}/complete", json={}, headers=auth_headers
    )  # 모바일은 빈 객체
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data) == {"todo", "goal_progress", "personal_streak"}
    assert data["todo"]["status"] == "done"
    assert data["todo"]["actual_minutes"] == 60  # estimated 로 채움
    assert data["todo"]["completed_at"].endswith("+09:00")
    first_completed_at = data["todo"]["completed_at"]
    assert data["goal_progress"]["goal_id"] == goal.goal_id
    assert data["goal_progress"]["done_count"] == 1
    assert data["goal_progress"]["current_week_done"] == 1
    assert data["goal_progress"]["current_week_target"] == 3
    assert data["goal_progress"]["target_count"] == 12

    # 멱등: completed_at 갱신 없음
    r = await client.post(
        f"/v1/todos/{tid}/complete", json={"actual_minutes": 5}, headers=auth_headers
    )
    assert r.json()["data"]["todo"]["completed_at"] == first_completed_at
    assert r.json()["data"]["todo"]["actual_minutes"] == 60

    r = await client.post(f"/v1/todos/{tid}/uncomplete", headers=auth_headers)
    assert r.status_code == 204 and r.content == b""
    r = await client.get(f"/v1/todos/{tid}", headers=auth_headers)
    assert r.json()["data"]["status"] == "pending"
    assert r.json()["data"]["completed_at"] is None and r.json()["data"]["actual_minutes"] is None


async def test_complete_without_goal_has_null_progress(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    todo = await _create(client, auth_headers)
    r = await client.post(
        f"/v1/todos/{todo['todo_id']}/complete", headers=auth_headers
    )  # 본문 없음도 허용
    assert r.status_code == 200
    assert r.json()["data"]["goal_progress"] is None


async def test_postpone(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    todo = await _create(client, auth_headers)
    tid = todo["todo_id"]
    tomorrow = service_today() + timedelta(days=1)

    r = await client.post(f"/v1/todos/{tid}/postpone", headers=auth_headers)  # to_date 생략 → +1
    assert r.status_code == 200
    data = r.json()["data"]
    assert (
        data["date"] == tomorrow.isoformat() and data["postpone_count"] == 1 and data["order"] == 1
    )

    r = await client.post(
        f"/v1/todos/{tid}/postpone", json={"to_date": tomorrow.isoformat()}, headers=auth_headers
    )
    assert r.status_code == 400 and "to_date" in r.json()["error"]["details"]

    await client.post(f"/v1/todos/{tid}/complete", headers=auth_headers)
    r = await client.post(f"/v1/todos/{tid}/postpone", headers=auth_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "TODO_ALREADY_DONE"


async def test_todos_require_auth(client: AsyncClient) -> None:
    r = await client.get("/v1/todos")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"
