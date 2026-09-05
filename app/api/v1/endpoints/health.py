"""GET /health — 인증 없음. Railway 헬스체크와 로컬 연결 확인용 (§3)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.response import ok
from app.db.redis import get_redis
from app.db.session import get_engine

router = APIRouter(tags=["health"])

Probe = Callable[[], Awaitable[None]]
PROBE_TIMEOUT_SECONDS = 2.0


async def probe_db() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def probe_redis() -> None:
    pong = await get_redis().ping()
    if not pong:
        raise RuntimeError("PING 응답이 없습니다.")


def get_probes() -> dict[str, Probe]:
    """테스트에서 Depends 로 교체한다. 실제 DB·Redis 없이도 핸들러를 검증하기 위해."""
    return {"db": probe_db, "redis": probe_redis}


async def _run(probe: Probe) -> str:
    try:
        await asyncio.wait_for(probe(), timeout=PROBE_TIMEOUT_SECONDS)
        return "ok"
    except Exception:
        return "down"


@router.get(
    "/health",
    summary="서버·PostgreSQL·Redis 연결 상태",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "data": {"status": "ok", "db": "ok", "redis": "ok", "version": "0.1.0"}
                    }
                }
            }
        },
        503: {
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "HEALTH_CHECK_FAILED",
                            "message": "일부 서비스에 연결할 수 없어요.",
                            "details": {"db": "ok", "redis": "down"},
                        }
                    }
                }
            }
        },
    },
)
async def health(probes: Annotated[dict[str, Probe], Depends(get_probes)]) -> dict[str, Any]:
    names = list(probes)
    results = await asyncio.gather(*(_run(probes[name]) for name in names))
    status = dict(zip(names, results, strict=True))

    if any(value != "ok" for value in status.values()):
        # 의존 서비스가 내려가 있으면 성공으로 가장하지 않는다.
        raise AppError("HEALTH_CHECK_FAILED", details=status)

    return ok({"status": "ok", **status, "version": get_settings().app_version})
