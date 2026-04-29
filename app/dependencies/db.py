from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory

_factory = None


def _get_factory():
    global _factory
    if _factory is None:
        _factory = get_session_factory()
    return _factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _get_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
