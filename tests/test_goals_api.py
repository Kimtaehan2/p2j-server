"""/goals/* — 모바일 GoalApi.fetchActive() 계약 + 명세 §4."""

from datetime import timedelta

from httpx import AsyncClient

from app.core.time import service_today

RECURRING = {
    "title": "주 3회 운동하기",
    "type": "recurring",
    "color": "#3182F6",
    "frequency": {"times": 3, "per": "week"},
    "duration_weeks": 4,
    "estimated_minutes": 60,
}


async def test_create_recurring_computes_end_date(client: AsyncClient, auth_headers) -> None:
    r = await client.post("/v1/goals", json=RECURRING, headers=auth_headers)
    assert r.status_code == 201, r.text
    g = r.json()["data"]
    today = service_today()
    assert g["start_date"] == today.isoformat()
    assert g["end_date"] == (today + timedelta(days=27)).isoformat()
    assert g["frequency"] == {"times": 3, "per": "week"}
    assert g["status"] == "active" and g["color"] == "#3182F6"
    assert g["progress"] == {
        "goal_id": g["goal_id"],
        "target_count": 12,
        "done_count": 0,
        "achievement_rate": 0.0,
        "current_week_done": 0,
        "current_week_target": 3,
    }
    assert g["created_at"].endswith("+09:00")


async def test_create_single_defaults(client: AsyncClient, auth_headers) -> None:
    r = await client.post("/v1/goals", json={"title": "토익 접수"}, headers=auth_headers)
    g = r.json()["data"]
    assert g["type"] == "single"
    assert g["frequency"] is None and g["duration_weeks"] is None and g["end_date"] is None
    assert g["color"].startswith("#") and len(g["color"]) == 7  # 팔레트 순환
    assert g["progress"]["target_count"] == 1


async def test_create_validation(client: AsyncClient, auth_headers) -> None:
    r = await client.post(
        "/v1/goals", json={"title": "x", "type": "recurring"}, headers=auth_headers
    )
    assert r.status_code == 400 and "frequency" in r.json()["error"]["details"]
    r = await client.post("/v1/goals", json={"title": "x", "color": "blue"}, headers=auth_headers)
    assert r.status_code == 400 and "color" in r.json()["error"]["details"]
    r = await client.post("/v1/goals", json={"title": "a" * 51}, headers=auth_headers)
    assert (
        r.status_code == 400
        and r.json()["error"]["details"]["title"] == "50자 이하로 입력해 주세요."
    )


async def test_list_with_status_filter_and_cursor(client: AsyncClient, auth_headers) -> None:
    ids = []
    for i in range(3):
        r = await client.post("/v1/goals", json={"title": f"목표 {i}"}, headers=auth_headers)
        ids.append(r.json()["data"]["goal_id"])
    await client.post(f"/v1/goals/{ids[0]}/archive", headers=auth_headers)

    r = await client.get("/v1/goals", params={"status": "active"}, headers=auth_headers)
    body = r.json()
    assert [g["goal_id"] for g in body["data"]] == [ids[2], ids[1]]  # 최신순
    assert body["page"] == {"next_cursor": None, "has_next": False}

    r = await client.get("/v1/goals", params={"limit": 2}, headers=auth_headers)
    body = r.json()
    assert len(body["data"]) == 2 and body["page"]["has_next"] is True
    r = await client.get(
        "/v1/goals",
        params={"limit": 2, "cursor": body["page"]["next_cursor"]},
        headers=auth_headers,
    )
    assert [g["goal_id"] for g in r.json()["data"]] == [ids[0]]
    assert r.json()["page"]["has_next"] is False

    r = await client.get("/v1/goals", params={"cursor": "%%%"}, headers=auth_headers)
    assert r.status_code == 400 and "cursor" in r.json()["error"]["details"]


async def test_get_patch_archive(client: AsyncClient, auth_headers) -> None:
    gid = (await client.post("/v1/goals", json=RECURRING, headers=auth_headers)).json()["data"][
        "goal_id"
    ]

    r = await client.get(f"/v1/goals/{gid}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["data"]["title"] == RECURRING["title"]

    r = await client.patch(
        f"/v1/goals/{gid}",
        json={"title": "주 3회 러닝", "duration_weeks": 2, "status": "completed"},
        headers=auth_headers,
    )
    g = r.json()["data"]
    assert g["title"] == "주 3회 러닝" and g["status"] == "completed"
    assert g["end_date"] == (service_today() + timedelta(days=13)).isoformat()
    assert g["progress"]["target_count"] == 6

    r = await client.patch(f"/v1/goals/{gid}", json={"status": "archived"}, headers=auth_headers)
    assert r.status_code == 400  # 보관은 /archive 로

    r = await client.post(f"/v1/goals/{gid}/archive", headers=auth_headers)
    assert r.json()["data"]["status"] == "archived"
    r = await client.patch(f"/v1/goals/{gid}", json={"status": "active"}, headers=auth_headers)
    assert r.json()["data"]["status"] == "active"  # 보관 해제


async def test_delete_detaches_todos(client: AsyncClient, auth_headers) -> None:
    gid = (
        await client.post("/v1/goals", json={"title": "삭제될 목표"}, headers=auth_headers)
    ).json()["data"]["goal_id"]
    todo = (
        await client.post("/v1/todos", json={"title": "x", "goal_id": gid}, headers=auth_headers)
    ).json()["data"]
    assert todo["goal_title"] == "삭제될 목표"

    r = await client.delete(f"/v1/goals/{gid}", headers=auth_headers)
    assert r.status_code == 204
    assert (await client.get(f"/v1/goals/{gid}", headers=auth_headers)).status_code == 404
    t = (await client.get(f"/v1/todos/{todo['todo_id']}", headers=auth_headers)).json()["data"]
    assert t["goal_id"] is None and t["goal_title"] is None


async def test_progress_reflects_completed_todos(client: AsyncClient, auth_headers) -> None:
    gid = (await client.post("/v1/goals", json=RECURRING, headers=auth_headers)).json()["data"][
        "goal_id"
    ]
    for _ in range(2):
        t = (
            await client.post(
                "/v1/todos", json={"title": "운동", "goal_id": gid}, headers=auth_headers
            )
        ).json()["data"]
        await client.post(f"/v1/todos/{t['todo_id']}/complete", headers=auth_headers)
    p = (await client.get(f"/v1/goals/{gid}", headers=auth_headers)).json()["data"]["progress"]
    assert p["done_count"] == 2 and p["current_week_done"] == 2
    assert p["achievement_rate"] == round(2 / 12, 2)


async def test_goal_of_other_user_is_404(client: AsyncClient, auth_headers) -> None:
    r = await client.get("/v1/goals/999999", headers=auth_headers)
    assert r.status_code == 404 and r.json()["error"]["code"] == "GOAL_NOT_FOUND"
