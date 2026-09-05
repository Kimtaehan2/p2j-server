"""GET /v1/health — 의존 서비스가 내려가 있으면 성공으로 가장하지 않는다."""

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.endpoints.health import get_probes


async def _up() -> None:
    return None


async def _down() -> None:
    raise ConnectionError("connection refused")


async def test_health_ok(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_probes] = lambda: {"db": _up, "redis": _up}
    r = await client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["db"] == "ok"
    assert body["data"]["redis"] == "ok"
    assert "version" in body["data"]


async def test_health_degraded_is_503(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_probes] = lambda: {"db": _up, "redis": _down}
    r = await client.get("/v1/health")
    assert r.status_code == 503
    assert r.json()["error"] == {
        "code": "HEALTH_CHECK_FAILED",
        "message": "일부 서비스에 연결할 수 없어요.",
        "details": {"db": "ok", "redis": "down"},
    }


async def test_openapi_is_served_unwrapped(client: AsyncClient) -> None:
    r = await client.get("/v1/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "/v1/health" in spec["paths"]
    assert "/v1/auth/me" in spec["paths"]
