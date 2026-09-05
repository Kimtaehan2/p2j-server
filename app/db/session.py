"""async engine 과 sessionmaker.

엔진은 프로세스에 하나. 첫 사용 시 만들고 lifespan 종료 때 dispose 한다.
테스트는 `set_engine()` 으로 SQLite 엔진을 끼워 넣는다.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


def set_engine(engine: AsyncEngine | None) -> None:
    """테스트 전용. 엔진을 바꾸면 세션 팩토리도 다시 만든다."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = None


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
