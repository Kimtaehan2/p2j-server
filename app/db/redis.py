"""Redis 클라이언트 (redis-py asyncio). 프로세스에 하나만 둔다.

연결은 첫 명령 때 맺어진다. Redis 가 내려가 있어도 서버는 뜨고 /health 가 503 으로 알린다.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
