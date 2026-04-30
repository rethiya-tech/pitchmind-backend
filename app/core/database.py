from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    return create_async_engine(url, poolclass=NullPool, echo=False)


def get_engine():
    return _make_engine(get_settings().DATABASE_URL)


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
