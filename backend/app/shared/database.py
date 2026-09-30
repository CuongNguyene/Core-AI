from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base metadata for future SQLAlchemy models."""


class Database:
    """Owns the async database engine and sessions for this application process."""

    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def check_connection(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()
