from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().DATABASE_URL,
            pool_size=3,
            max_overflow=7,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_session_factory(engine=None):
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory
