from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.integration.nonce_store import ActorContextNonceRecord, SqlAlchemyActorContextNonceStore
from app.shared.database import Base


@pytest.mark.asyncio
async def test_sql_nonce_store_rejects_replay_across_store_instances() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all, tables=[ActorContextNonceRecord.__table__]
            )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        first_instance = SqlAlchemyActorContextNonceStore(session_factory)
        second_instance = SqlAlchemyActorContextNonceStore(session_factory)
        expires_at = datetime.now(UTC) + timedelta(seconds=60)

        assert await first_instance.consume("shared-nonce", expires_at) is True
        assert await second_instance.consume("shared-nonce", expires_at) is False
    finally:
        await engine.dispose()
