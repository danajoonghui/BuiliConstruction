from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .core.config import Settings, get_settings


def _make_engine(settings: Settings) -> AsyncEngine:
    if settings.is_sqlite:
        db_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=False,
        connect_args={"check_same_thread": False} if settings.is_sqlite else {},
    )
    if settings.is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine


settings = get_settings()
engine = _make_engine(settings)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def database_ready() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
