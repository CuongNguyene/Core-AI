"""Durable replay protection for signed LMS actor contexts."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class ActorContextNonceRecord(Base):
    __tablename__ = "actor_context_nonces"

    nonce: Mapped[str] = mapped_column(String(128), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ActorContextNonceStoreUnavailable(RuntimeError):
    """The durable store cannot protect an incoming signed context."""


class SqlAlchemyActorContextNonceStore:
    """Atomically consume nonces across every API instance sharing the database."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def consume(self, nonce: str, expires_at: datetime) -> bool:
        try:
            async with self._session_factory() as session:
                await session.execute(
                    delete(ActorContextNonceRecord).where(
                        ActorContextNonceRecord.expires_at < datetime.now(UTC)
                    )
                )
                session.add(ActorContextNonceRecord(nonce=nonce, expires_at=expires_at))
                await session.commit()
                return True
        except IntegrityError:
            await session.rollback()
            return False
        except SQLAlchemyError as exc:
            raise ActorContextNonceStoreUnavailable(
                "actor_context_nonce_store_unavailable"
            ) from exc


class InMemoryActorContextNonceStore:
    """Test fallback only; production must configure the SQLAlchemy store."""

    def __init__(self) -> None:
        self._nonces: dict[str, datetime] = {}

    async def consume(self, nonce: str, expires_at: datetime) -> bool:
        if nonce in self._nonces:
            return False
        self._nonces[nonce] = expires_at
        return True
