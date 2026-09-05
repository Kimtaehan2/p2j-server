"""p2j-mobile 연동 계약 재현 테스트.

Flutter 가 없는 환경에서, 모바일 코드(AuthApi · TodoApi · GoalApi · AuthInterceptor)가 보내는
요청을 **그대로** 실서버에 보내고 응답을 Dart freezed 모델의 규칙으로 검증한다.

    uv run python tests/contract/mobile_replay.py [http://127.0.0.1:8000/v1]

검증 기준 (p2j-mobile main 브랜치 기준):
- ApiResponse.object: body["data"] 가 Map 이어야 한다. list: List.
- User.fromJson: user_id(int) · nickname(String) · today(String) 필수.
  created_at 은 DateTime.parse 가능해야 한다.
- AuthSession.fromJson: access_token · refresh_token · user 필수.
- Todo.fromJson: todo_id · title · date 필수. status/source 는 모르는 값이면 unknown 폴백.
- DayTodos.fromJson: date 필수. DayAchievement: date 필수.
- Goal.fromJson: goal_id · title 필수.
- ApiException.fromResponse: error.code · error.message, details[field] 는 String 또는 List.
- AuthInterceptor: 401 이고 code 가 INVALID_CREDENTIALS 가 아니면 /auth/refresh 후 1회 재시도.
- uncomplete / delete / logout 은 204 본문 없음. logout 은 본문 없이 POST.
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime
from typing import Any

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1"
ISO_KST = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")
results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def dart_datetime_ok(value: Any) -> bool:
    # Dart DateTime.parse 는 ISO 8601 + 오프셋을 받는다. 서버는 항상 +09:00 로 준다 (§1.1).
    if value is None:
        return True
    try:
        datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return bool(ISO_KST.match(value))


def is_snake(obj: Any) -> bool:
    if isinstance(obj, dict):
        return all(re.fullmatch(r"[a-z0-9_]+", k) for k in obj) and all(
            is_snake(v) for v in obj.values()
        )
    if isinstance(obj, list):
        return all(is_snake(v) for v in obj)
    return True


def validate_user(u: dict[str, Any], where: str) -> None:
    check(
        f"{where}: User 필수 필드",
        isinstance(u.get("user_id"), int)
        and isinstance(u.get("nickname"), str)
        and isinstance(u.get("today"), str),
        str(u),
    )
    check(
        f"{where}: User.today 는 YYYY-MM-DD",
        bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", u.get("today", ""))),
    )
    check(
        f"{where}: User.created_at DateTime.parse 가능(+09:00)",
        dart_datetime_ok(u.get("created_at")),
        str(u.get("created_at")),
    )
    check(f"{where}: User 에 email 없음(노출 금지)", "email" not in u and "password_hash" not in u)


def validate_session(s: dict[str, Any], where: str) -> None:
    check(
        f"{where}: AuthSession 필수 필드",
        all(isinstance(s.get(k), str) for k in ("access_token", "refresh_token"))
        and isinstance(s.get("user"), dict),
        str(list(s)),
    )
    check(
        f"{where}: expires_in int, token_type Bearer",
        isinstance(s.get("expires_in"), int) and s.get("token_type") == "Bearer",
    )
    validate_user(s["user"], where)


def validate_todo(t: dict[str, Any], where: str) -> None:
    check(
        f"{where}: Todo 필수 필드",
        isinstance(t.get("todo_id"), int)
        and isinstance(t.get("title"), str)
        and isinstance(t.get("date"), str),
        str(t),
    )
    check(
        f"{where}: Todo.status 는 모바일 enum 값",
        t.get("status") in ("pending", "done", "deferred", "skipped"),
        str(t.get("status")),
    )
    check(
        f"{where}: Todo.source 는 모바일 enum 값",
        t.get("source") in ("manual", "ai_suggested", "auto_scheduled"),
        str(t.get("source")),
    )
    check(
        f"{where}: Todo.order int, is_declared bool",
        isinstance(t.get("order"), int) and isinstance(t.get("is_declared"), bool),
    )
    check(
        f"{where}: Todo.completed_at DateTime.parse 가능",
        dart_datetime_ok(t.get("completed_at")),
        str(t.get("completed_at")),
    )
    for k in ("goal_id", "estimated_minutes", "actual_minutes"):
        check(f"{where}: Todo.{k} int 또는 null", t.get(k) is None or isinstance(t.get(k), int))
    check(
        f"{where}: Todo.goal_title String 또는 null",
        t.get("goal_title") is None or isinstance(t.get("goal_title"), str),
    )


def validate_goal(g: dict[str, Any], where: str) -> None:
    check(
        f"{where}: Goal 필수 필드",
        isinstance(g.get("goal_id"), int) and isinstance(g.get("title"), str),
        str(g),
    )
    p = g.get("progress")
    check(
        f"{where}: Goal.progress 객체 + 5개 숫자 필드",
        isinstance(p, dict)
        and all(
            isinstance(p.get(k), (int, float))
            for k in (
                "target_count",
                "done_count",
                "achievement_rate",
                "current_week_done",
                "current_week_target",
            )
        ),
        str(p),
    )
    f = g.get("frequency")
    check(
        f"{where}: Goal.frequency null 또는 {{times,per}}",
        f is None or (isinstance(f.get("times"), int) and f.get("per") in ("week", "month")),
        str(f),
    )
    check(f"{where}: Goal.created_at DateTime.parse 가능", dart_datetime_ok(g.get("created_at")))


def error_of(r: httpx.Response) -> dict[str, Any]:
    body = r.json()
    check(
        f"{r.request.method} {r.request.url.path} 오류 본문은 {{error:{{code,message}}}}",
        isinstance(body.get("error"), dict)
        and isinstance(body["error"].get("code"), str)
        and isinstance(body["error"].get("message"), str),
        r.text,
    )
    return body["error"]


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=15)
    email = f"mobile-{uuid.uuid4().hex[:8]}@p2j.dev"
    today = None

    # ---- 회원가입 화면: AuthApi.signup -----------------------------------------------
    r = c.post("/auth/signup", json={"email": email, "password": "password123", "nickname": "지호"})
    check("signup 2xx (Dio validateStatus 200~299)", 200 <= r.status_code < 300, r.text)
    check("응답 키가 전부 snake_case", is_snake(r.json()))
    session = r.json()["data"]
    validate_session(session, "signup")
    today = session["user"]["today"]
    access, refresh = session["access_token"], session["refresh_token"]
    auth = {"Authorization": f"Bearer {access}"}

    # 회원가입 화면의 오류 표시: fieldMessage('email'), WEAK_PASSWORD, EMAIL_ALREADY_EXISTS
    r = c.post("/auth/signup", json={"email": "nope", "password": "password123", "nickname": "x"})
    e = error_of(r)
    check(
        "잘못된 이메일 → 400 VALIDATION_ERROR + details.email 문자열",
        r.status_code == 400
        and e["code"] == "VALIDATION_ERROR"
        and isinstance(e.get("details", {}).get("email"), str),
        r.text,
    )
    r = c.post("/auth/signup", json={"email": "a@b.c", "password": "short", "nickname": "x"})
    check(
        "짧은 비밀번호 → 400 WEAK_PASSWORD",
        r.status_code == 400 and error_of(r)["code"] == "WEAK_PASSWORD",
    )
    r = c.post(
        "/auth/signup", json={"email": email.upper(), "password": "password123", "nickname": "x"}
    )
    e = error_of(r)
    check(
        "중복 이메일(대문자) → 409 EMAIL_ALREADY_EXISTS + details.email",
        r.status_code == 409
        and e["code"] == "EMAIL_ALREADY_EXISTS"
        and "email" in e.get("details", {}),
    )

    # ---- 로그인 화면: AuthApi.login --------------------------------------------------
    r = c.post("/auth/login", json={"email": email, "password": "password123"})
    check("login 200", r.status_code == 200, r.text)
    validate_session(r.json()["data"], "login")
    r = c.post("/auth/login", json={"email": email, "password": "wrong-pass"})
    check(
        "비밀번호 틀림 → 401 INVALID_CREDENTIALS (AuthInterceptor 가 refresh 안 함)",
        r.status_code == 401 and error_of(r)["code"] == "INVALID_CREDENTIALS",
    )

    # ---- 앱 복귀: AuthApi.fetchMe -----------------------------------------------------
    r = c.get("/auth/me", headers=auth)
    check("GET /auth/me 200", r.status_code == 200, r.text)
    validate_user(r.json()["data"], "me")
    check(
        "me.today == signup.user.today (serverTodayProvider 일관성)",
        r.json()["data"]["today"] == today,
    )

    # ---- 홈 화면 동시 호출: fetchMe · fetchDay(today) · fetchWeek() · goals?status=active --
    r = c.get("/todos", params={"date": today}, headers=auth)
    check("GET /todos?date= 200", r.status_code == 200, r.text)
    day = r.json()["data"]
    check(
        "DayTodos.date 필수, items 리스트, summary 객체",
        day.get("date") == today
        and isinstance(day.get("items"), list)
        and isinstance(day.get("summary"), dict),
    )
    s = day["summary"]
    check(
        "TodoSummary 4필드 (total, done int / achievement_rate num / total_estimated_minutes int)",
        isinstance(s.get("total"), int)
        and isinstance(s.get("done"), int)
        and isinstance(s.get("achievement_rate"), (int, float))
        and isinstance(s.get("total_estimated_minutes"), int),
        str(s),
    )

    r = c.get("/todos/week", headers=auth)  # 모바일은 start_date 를 보내지 않는다
    check(
        "GET /todos/week 200, data 는 List (ApiResponse.list)",
        r.status_code == 200 and isinstance(r.json()["data"], list),
    )
    week = r.json()["data"]
    check(
        "week 는 7칸, 마지막이 today",
        len(week) == 7 and week[-1]["date"] == today,
        str([d["date"] for d in week]),
    )
    check(
        "DayAchievement 필드 (date, total, done, achievement_rate)",
        all(
            isinstance(d.get("date"), str)
            and isinstance(d.get("total"), int)
            and isinstance(d.get("done"), int)
            and isinstance(d.get("achievement_rate"), (int, float))
            for d in week
        ),
    )

    r = c.get("/goals", params={"status": "active"}, headers=auth)
    check(
        "GET /goals?status=active 200, data 는 List, page 객체",
        r.status_code == 200
        and isinstance(r.json()["data"], list)
        and isinstance(r.json().get("page"), dict),
        r.text,
    )

    # 목표를 하나 만들어 두고(모바일은 아직 create 없음, 서버 기능) 목록·TODO 조인 확인
    r = c.post(
        "/goals",
        json={
            "title": "주 3회 운동하기",
            "type": "recurring",
            "frequency": {"times": 3, "per": "week"},
            "duration_weeks": 4,
            "estimated_minutes": 60,
        },
        headers=auth,
    )
    goal = r.json()["data"]
    validate_goal(goal, "POST /goals")
    r = c.get("/goals", params={"status": "active"}, headers=auth)
    goals = r.json()["data"]
    check("goals 목록에 생성한 목표가 보인다", any(g["goal_id"] == goal["goal_id"] for g in goals))
    for g in goals:
        validate_goal(g, "GET /goals")

    # ---- 투두 추가 시트: TodoApi.create(title, date, estimated_minutes) --------------
    r = c.post(
        "/todos",
        json={"title": "백준 실버 2문제", "date": today, "estimated_minutes": 45},
        headers=auth,
    )
    check("POST /todos 2xx", 200 <= r.status_code < 300, r.text)
    todo = r.json()["data"]
    validate_todo(todo, "create")
    r = c.post(
        "/todos", json={"title": "헬스", "date": today, "goal_id": goal["goal_id"]}, headers=auth
    )
    todo2 = r.json()["data"]
    check(
        "goal_id 붙인 투두의 goal_title 조인", todo2["goal_title"] == "주 3회 운동하기", str(todo2)
    )
    r = c.post("/todos", json={"title": "   ", "date": today}, headers=auth)
    e = error_of(r)
    check(
        "빈 제목 → 400 VALIDATION_ERROR + details.title 문자열(입력칸 아래 표시)",
        r.status_code == 400 and isinstance(e.get("details", {}).get("title"), str),
        r.text,
    )

    # ---- 제목 수정: TodoApi.updateTitle -----------------------------------------------
    r = c.patch(f"/todos/{todo['todo_id']}", json={"title": "백준 골드 1문제"}, headers=auth)
    check(
        "PATCH /todos/{id} {title} 200 + Todo",
        r.status_code == 200 and r.json()["data"]["title"] == "백준 골드 1문제",
        r.text,
    )
    validate_todo(r.json()["data"], "patch")

    # ---- 완료 체크: TodoApi.complete → data.todo -------------------------------------------
    r = c.post(f"/todos/{todo['todo_id']}/complete", json={}, headers=auth)
    check("POST complete 200", r.status_code == 200, r.text)
    body = r.json()["data"]
    check(
        "complete 응답에 todo 키 (모바일이 data.todo 우선 읽음)",
        isinstance(body.get("todo"), dict) and body["todo"]["status"] == "done",
    )
    validate_todo(body["todo"], "complete.todo")
    check(
        "complete 응답에 goal_progress(null 허용) · personal_streak(int)",
        "goal_progress" in body and isinstance(body.get("personal_streak"), int),
    )
    r = c.post(f"/todos/{todo2['todo_id']}/complete", json={}, headers=auth)
    gp = r.json()["data"]["goal_progress"]
    check(
        "목표 있는 투두 완료 → goal_progress 채워짐",
        isinstance(gp, dict) and gp["goal_id"] == goal["goal_id"] and gp["done_count"] == 1,
        str(gp),
    )

    # 홈 재조회: summary 가 서버에서 재계산되어 있어야 한다
    r = c.get("/todos", params={"date": today}, headers=auth)
    s = r.json()["data"]["summary"]
    # 목표의 estimated_minutes 는 AI 파싱 기본값일 뿐, POST /todos 가 상속하지 않는다 (§4). 45 + 0.
    check(
        "완료 후 summary 재계산 (total 2, done 2, rate 1.0, minutes 45)",
        s == {"total": 2, "done": 2, "achievement_rate": 1.0, "total_estimated_minutes": 45},
        str(s),
    )
    for t in r.json()["data"]["items"]:
        validate_todo(t, "list.items")

    # ---- 완료 취소: TodoApi.uncomplete → 204 (모바일이 summary 로컬 재계산) --------------
    r = c.post(f"/todos/{todo['todo_id']}/uncomplete", headers=auth)
    check("POST uncomplete 204 본문 없음", r.status_code == 204 and r.content == b"")

    # ---- 삭제: TodoApi.delete → 204 -------------------------------------------------
    r = c.delete(f"/todos/{todo['todo_id']}", headers=auth)
    check("DELETE /todos/{id} 204 본문 없음", r.status_code == 204 and r.content == b"")
    r = c.get(f"/todos/{todo['todo_id']}", headers=auth)
    check(
        "삭제 후 조회 → 404 TODO_NOT_FOUND",
        r.status_code == 404 and error_of(r)["code"] == "TODO_NOT_FOUND",
    )

    # ---- AuthInterceptor 흐름: 401 → /auth/refresh {refresh_token} → 재시도 ----------------
    r = c.get(
        "/todos", params={"date": today}, headers={"Authorization": "Bearer expired.or.garbage"}
    )
    e = error_of(r)
    check(
        "깨진 토큰 → 401 + code 가 INVALID_CREDENTIALS 아님 (→ 재발급 시도 대상)",
        r.status_code == 401 and e["code"] in ("UNAUTHORIZED", "TOKEN_EXPIRED"),
        r.text,
    )
    r = c.post("/auth/refresh", json={"refresh_token": refresh})  # 헤더 없이 (모바일 refreshDio)
    check("POST /auth/refresh 200", r.status_code == 200, r.text)
    rot = r.json()["data"]
    check(
        "refresh 응답에 access_token · refresh_token(rotation)",
        isinstance(rot.get("access_token"), str)
        and isinstance(rot.get("refresh_token"), str)
        and rot["refresh_token"] != refresh,
    )
    r = c.get(
        "/todos", params={"date": today}, headers={"Authorization": f"Bearer {rot['access_token']}"}
    )
    check("새 access 로 재시도 성공", r.status_code == 200)
    r = c.post("/auth/refresh", json={"refresh_token": refresh})
    check("이전 refresh 재사용 → 401 (모바일은 세션 만료 처리)", r.status_code == 401)

    # ---- 로그아웃: AuthApi.logout — 본문 없이 POST, 헤더는 붙음 -------------------------
    r = c.post("/auth/login", json={"email": email, "password": "password123"})
    fresh = r.json()["data"]
    r = c.post("/auth/logout", headers={"Authorization": f"Bearer {fresh['access_token']}"})
    check("POST /auth/logout (본문 없음) 204", r.status_code == 204 and r.content == b"", r.text)

    # ---- Flutter web 개발용 CORS preflight ---------------------------------------------
    r = c.options(
        "/todos",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    check(
        "CORS preflight 허용 (flutter run -d chrome)",
        r.status_code in (200, 204)
        and r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173"),
        f"{r.status_code} {dict(r.headers)}",
    )

    # ---- 없는 경로 / 서버 오류 형식 ----------------------------------------------------
    r = c.get("/nope", headers=auth)
    check(
        "없는 경로 → JSON 404 NOT_FOUND (HTML 아님)",
        r.status_code == 404 and error_of(r)["code"] == "NOT_FOUND",
    )

    failed = [x for x in results if not x[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    for name, _, detail in failed:
        print(f"  FAIL {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
