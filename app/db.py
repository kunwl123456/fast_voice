from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

Base = declarative_base()


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def _create_async_engine() -> AsyncEngine:
    """
    Web API 层使用 AsyncEngine/AsyncSession：
    - Postgres: postgresql+asyncpg://...
    - SQLite:   sqlite+aiosqlite:///...
    """
    url = settings.database_url
    if _is_sqlite(url):
        return create_async_engine(url, pool_pre_ping=True)
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=int(settings.db_pool_size),
        max_overflow=int(settings.db_max_overflow),
        pool_timeout=int(settings.db_pool_timeout_seconds),
        pool_recycle=int(settings.db_pool_recycle_seconds),
    )


engine: AsyncEngine = _create_async_engine()
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=engine, expire_on_commit=False)


