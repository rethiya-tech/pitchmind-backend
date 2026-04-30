import ssl as _ssl

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    # Strip ?ssl=* query params and handle SSL via connect_args
    clean_url = url.split("?")[0]
    if "render.com" in url or "onrender.com" in url or any(
        h in url for h in ["dpg-", "oregon-postgres", "singapore-postgres"]
    ):
        ssl_ctx = _ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = _ssl.CERT_NONE
        return create_async_engine(clean_url, poolclass=NullPool, echo=False, connect_args={"ssl": ssl_ctx})
    return create_async_engine(clean_url, poolclass=NullPool, echo=False)


def get_engine():
    return _make_engine(get_settings().DATABASE_URL)


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
