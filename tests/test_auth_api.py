"""/auth/* — 모바일 AuthApi · AuthInterceptor 가 기대하는 계약 그대로."""

from httpx import AsyncClient

SIGNUP = {"email": "New@P2J.dev", "password": "password123", "nickname": "  지호 "}


async def test_signup_returns_session_with_user_today(client: AsyncClient, clean_tables) -> None:
    r = await client.post("/v1/auth/signup", json=SIGNUP)
    assert r.status_code == 200  # 201 이 아니다 (§3)
    data = r.json()["data"]
    assert set(data) == {"access_token", "refresh_token", "token_type", "expires_in", "user"}
    assert data["expires_in"] == 1800
    assert data["user"]["nickname"] == "지호"  # 공백 제거
    assert len(data["user"]["today"]) == 10
    assert "email" not in data["user"]

    # 발급된 access 로 바로 /auth/me
    me = await client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["data"]["user_id"] == data["user"]["user_id"]


async def test_signup_duplicate_email_case_insensitive(client: AsyncClient, clean_tables) -> None:
    await client.post("/v1/auth/signup", json=SIGNUP)
    r = await client.post("/v1/auth/signup", json={**SIGNUP, "email": "new@p2j.dev"})
    assert r.status_code == 409
    body = r.json()["error"]
    assert body["code"] == "EMAIL_ALREADY_EXISTS"
    assert body["details"]["email"] == "이미 가입된 이메일이에요."


async def test_signup_weak_password(client: AsyncClient, clean_tables) -> None:
    r = await client.post("/v1/auth/signup", json={**SIGNUP, "password": "short"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "WEAK_PASSWORD"
    assert r.json()["error"]["details"] == {}


async def test_signup_validation(client: AsyncClient, clean_tables) -> None:
    r = await client.post(
        "/v1/auth/signup", json={"email": "nope", "password": "password123", "nickname": ""}
    )
    assert r.status_code == 400
    details = r.json()["error"]["details"]
    assert set(details) == {"email", "nickname"}
    assert details["nickname"] == "1자 이상 입력해 주세요."


async def test_login_and_wrong_password(client: AsyncClient, clean_tables) -> None:
    await client.post("/v1/auth/signup", json=SIGNUP)

    ok = await client.post(
        "/v1/auth/login", json={"email": "new@p2j.dev", "password": "password123"}
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["user"]["nickname"] == "지호"

    for payload in (
        {"email": "new@p2j.dev", "password": "wrong-password"},
        {"email": "ghost@p2j.dev", "password": "password123"},
    ):
        bad = await client.post("/v1/auth/login", json=payload)
        assert bad.status_code == 401
        # 모바일은 이 코드만 재발급 없이 폼에 표시한다 (§1.3)
        assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_refresh_rotation_via_api(client: AsyncClient, clean_tables) -> None:
    session = (await client.post("/v1/auth/signup", json=SIGNUP)).json()["data"]

    r1 = await client.post("/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert r1.status_code == 200
    rotated = r1.json()["data"]
    assert set(rotated) == {"access_token", "refresh_token", "token_type", "expires_in"}
    assert rotated["refresh_token"] != session["refresh_token"]

    # 이전 토큰 재사용 → 401 UNAUTHORIZED, 그리고 새 토큰까지 전부 폐기
    r2 = await client.post("/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "UNAUTHORIZED"
    r3 = await client.post("/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert r3.status_code == 401


async def test_logout_is_204_and_idempotent(client: AsyncClient, clean_tables) -> None:
    session = (await client.post("/v1/auth/signup", json=SIGNUP)).json()["data"]
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    r = await client.post(
        "/v1/auth/logout", json={"refresh_token": session["refresh_token"]}, headers=headers
    )
    assert r.status_code == 204 and r.content == b""
    # 본문 없이도, 두 번째도 204
    assert (await client.post("/v1/auth/logout", headers=headers)).status_code == 204
    # 폐기된 refresh 로는 재발급 불가
    r = await client.post("/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert r.status_code == 401
