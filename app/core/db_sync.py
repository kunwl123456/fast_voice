from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _derive_sync_url(async_url: str) -> str:
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if async_url.startswith("sqlite+aiosqlite:///"):
        return async_url.replace("sqlite+aiosqlite:///", "sqlite+pysqlite:///", 1)
    if async_url.startswith("sqlite+aiosqlite://"):
        return async_url.replace("sqlite+aiosqlite://", "sqlite+pysqlite://", 1)
    # fallback: user should provide DATABASE_URL_SYNC explicitly
    return async_url


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def _create_engine():
    url = settings.database_url_sync or _derive_sync_url(settings.database_url)
    if _is_sqlite(url):
        return create_engine(
            url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=int(settings.db_pool_size),
        max_overflow=int(settings.db_max_overflow),
        pool_timeout=int(settings.db_pool_timeout_seconds),
        pool_recycle=int(settings.db_pool_recycle_seconds),
    )


engine_sync = _create_engine()
SessionLocalSync = sessionmaker(bind=engine_sync, autocommit=False, autoflush=False)


@contextmanager
def session_scope_sync():
    db: Session = SessionLocalSync()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
